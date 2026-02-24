# from module.sync_aria import fetch_plans
# from config import Config
import subprocess
import os
import tomllib
from sqlmodel import Session, create_engine, select
import logging

from module.dataclass.conquest_dataclass import (
	DICOMImages, 
	DICOMPatients,
	DICOMSeries
)

from module.interfaces import (
	aria_interface,
	conquest_interface
)

logging.basicConfig(
	filename="../export.log", 
	filemode='a', 
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	level=logging.INFO)

logger = logging.getLogger(__name__)

# Plans to fetch from Aria
# plans = fetch_plans()

fn = os.path.join(os.path.dirname(__file__), 'config/config.toml')
with open(fn, 'rb') as f:
    config = tomllib.load(f)

# FIND RT PLANS FROM SQL
# BUILD COMPLETE STUDY TREE
# DOWNLOAD RT PLANS
# DOWNLOAD ALL RT DOSE FILES
# FIND THE REFERENCED RT PLAN IN EACH DOSE FILE
# FIND THE REFERENCED STRUCTURE FILES IN THE RT PLAN
# DOWNLOAD THE STRUCTURE FILES
# DELETE THE UNINTERESTING RT DOSE FILES
# FIND THE REFERENCED CT FILES
# DOWNLOAD THE CONNECTED CT SERIES
# SEND TO MEDFYSHUS6666-2
# SEND TO KREST-HUS

plan_set = aria_interface.get_plan_set()

print(f"Found {len(plan_set) = } patients in SQL call")

data_dir = config["conquest"]["2"]["data_dir"]
transmitted = [k.split("\\")[-1] for k in glob(f"{data_dir}/*")]

for patient_ser in plan_set:
	print("Working on patient ", patient_ser)
	sent_dt = log_database.check_patient(patient_ser)

	if sent_dt:
		print(f"-> Patient has was transmitted at {sent_dt}")
		continue

	for plan_sop_uid in plan_set[patient_ser]["RTPLAN"]:
		patient_id = conquest_interface.get_patient_id_from_plan_sop_uid(plan_sop_uid)
		if patient_id:
			break

	if patient_id and patient_id in transmitted:
		print("Found patient in MEDFYSHUS6666-2 database")
		continue

	for plan_sop_uid in plan_set[patient_ser]["RTPLAN"]:
		# Move the treated RT Plans to Conquest
		print("Moving plan with SOP UID ", plan_sop_uid)

		assoc = aria_dicom_interface.get_assoc()
		aria_dicom_interface.c_move_image(assoc, plan_sop_uid)
		assoc.release()

		# Download the structure sets
		structure_sets, plan_label = conquest_interface.get_rt_struct_uid(plan_sop_uid)

		plan_set[patient_ser]["RTPlanLabel"].add(plan_label)

		for instance_uid in structure_sets:
			plan_set[patient_ser]["RTSTRUCT"].add(instance_uid)
			print(f"Moving structure set Instance UID {instance_uid}")

			assoc = aria_dicom_interface.get_assoc()
			aria_dicom_interface.c_move_image(assoc, instance_uid)
			assoc.release()

		# Download the associated CT
		for instance_uid in structure_sets:
			ct_series_uid_list = conquest_interface.find_referenced_ct_series(instance_uid)
			for ct_series_uid in ct_series_uid_list:
				plan_set[patient_ser]["CT"].add(ct_series_uid)

				assoc = aria_dicom_interface.get_assoc()
				aria_dicom_interface.c_move_series(assoc, ct_series_uid)
				assoc.release()

	# Build the complete study tree (also untreated plans)
	for plan_sop_uid in plan_set[patient_ser]["RTPLAN"]:
		assoc = aria_dicom_interface.get_assoc()
		result_set = conquest_interface.get_study_uid_from_plan_sop_uid(assoc, plan_sop_uid)
		if not len(result_set):
			continue

		study_uid = result_set[0]["StudyInstanceUID"]

		study_tree = aria_dicom_interface.c_find_study(assoc, study_uid)
		assoc.release()

		break
	
	print("Found ", len(study_tree), " series in the Study tree")

	# Download all RT DOSE objects
	all_dose_series_uid = list()
	for series in study_tree:
		if series.get("Modality") == "RTDOSE":
			rt_dose_uid = series.get("SeriesInstanceUID")
			all_dose_series_uid.append(rt_dose_uid)

			try:
				assoc = aria_dicom_interface.get_assoc()
				aria_dicom_interface.c_move_series(assoc, rt_dose_uid)
				assoc.release()
			except Exception as e:
				print(f"Could not move RT DOSE series with UID {rt_dose_uid = }... Skipping")

	rtdose_summary = dicom_db_interface.check_rtdose_beam_or_plansum(all_dose_series_uid)

	# Identify the connected RT Plan file UID for each RT Dose
	for rtdose_object in rtdose_summary:
		if not plan_set[patient_ser]["PatientID"]:
			plan_set[patient_ser]["PatientID"] = rtdose_object.get("PatientID")

		if rtdose_object.get("DoseSummationType") == "BEAM":
			continue

		rtdose_sop_instance_uid = rtdose_object.get("SOPInstanceUID")

		referenced_plan_instance_uids = rtdose_object.get("ReferencedRTlanSOPInstanceUID")

		for plan_uid in referenced_plan_instance_uids:
			if plan_uid in plan_set[patient_ser]["RTPLAN"]:
				plan_set[patient_ser]["RTDOSE"].add(rtdose_sop_instance_uid)

	plans_nb = len(plan_set[patient_ser]["RTPLAN"])
	rtdose_nb = len(plan_set[patient_ser]["RTDOSE"])

	print(f"Identified {rtdose_nb} dose object connected to {plans_nb} plans.")

	conquest_dicom_interface.c_move_to_medfys2(plan_set[patient_ser])
	conquest_dicom_interface.c_move_to_krest_hus(plan_set[patient_ser].get("PatientID"))
	
	log_database.add_patient(patient_ser, plan_set[patient_ser])

log_database.save()