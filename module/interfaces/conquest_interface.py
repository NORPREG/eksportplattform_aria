import hashlib
import logging
from configparser import ConfigParser
import shlex
import subprocess

from module.dataclass.conquest_dataclass import (
	DICOMImages, 
	DICOMPatients,
)
from sqlmodel import select

from config import Config
from pathlib import Path

config = Config()

logger = logging.getLogger(__name__ + f" (config.HF)")


# Conquest SQL Interface | Datamodel

def check_rtdose_beam_or_plansum_sql(rtdose_series_uid_list):
	rtdose_files = list()
	rtdose_output = list()

	with Session(engine) as session:
		for rtdose_series_uid in rtdose_series_uid_list:
			statement = select(DICOMImages).where(DICOMImages.SeriesInst == rtdose_series_uid)
			results = session.exec(statement).all()

			for result in results:
				rtdose_files.append(ROOT_DIR + result.ObjectFile)

	for f in rtdose_files:
		ds = pydicom.dcmread(f, stop_before_pixels=True)
		rtdose_output.append({
			"SOPInstanceUID": ds.SOPInstanceUID,
			"SeriesInstanceUID": ds.SeriesInstanceUID,
			"Modality": ds.Modality,
			"PatientID": ds.PatientID,
			"DoseSummationType": ds.DoseSummationType,
			"ReferencedRTlanSOPInstanceUID": [ k.ReferencedSOPInstanceUID for k in ds.ReferencedRTPlanSequence ]
		})

	return rtdose_output

def get_rt_struct_uid_sql(plan_sop_uid):
	with Session(engine) as session:
		statement = select(DICOMImages).where(DICOMImages.SOPInstanceUID == plan_sop_uid)
		result = session.exec(statement)
		try:
			ds_path = ROOT_DIR + result.one().ObjectFile
		except Exception as e:
			print("Cannot find structure files! ", e)
			return list()

	ds = pydicom.dcmread(ds_path)
	structure_sets = list()
	for seq in ds.ReferencedStructureSetSequence:
		structure_sets.append(seq.ReferencedSOPInstanceUID)
	
	if len(structure_sets) != 1:
		print(f"-----------  {len(structure_sets) = } --------- ")

	return structure_sets, ds.get("RTPlanLabel")


def get_patient_id_from_plan_sop_uid(plan_sop_uid: str) -> str:
	with Session(engine) as session:
		statement = select(DICOMImages).where(DICOMImages.SOPInstanceUID == plan_sop_uid)
		result = session.exec(statement).all()

		if not result:
			return None

		return result[0].ImagePat


def find_referenced_ct_series_sql(rtstruct_instance_uid):
	with Session(engine) as session:
		statement = select(DICOMImages).where(DICOMImages.SOPInstanceUID == rtstruct_instance_uid)
		result = session.exec(statement)
		try:
			ds_path = ROOT_DIR + result.one().ObjectFile
		except Exception as e:
			print("Cannot find CT series: ", e)
			return None

	ct_series_uid = set()
	ds = pydicom.dcmread(ds_path)
	for ref_frame_of_reference_seq in ds.ReferencedFrameOfReferenceSequence:
		for rt_ref_study_seq in ref_frame_of_reference_seq.RTReferencedStudySequence:
			for rt_ref_series_seq in rt_ref_study_seq.RTReferencedSeriesSequence:
				ct_series_uid.add(rt_ref_series_seq.SeriesInstanceUID)

	
	if len(ct_series_uid) != 1:
		print(f"-----------  {len(ct_series_uid) = } --------- ")

	return ct_series_uid

def find_referenced_plan_uid_from_rt_dose_sql(rt_dose_uid):
	with Session(engine) as session:
		statement = select(DICOMImages).where(DICOMImages.SeriesInst == rt_dose_uid)
		result = session.exec(statement)
		try:
			ds_path = ROOT_DIR + result.one().ObjectFile
		except:
			return list()

	plan_uid = list()

	ds = pydicom.dcmread(ds_path, stop_before_pixels=True)
	for seq in ds.ReferencedRTPlanSequence:
		plan_uid.append(seq.ReferencedSOPInstanceUID)

	if len(plan_uid) != 1:
		print(f"-----------  {len(plan_uid) = } --------- ")

	return plan_uid
