from pynetdicom import AE, evt, build_role
from pynetdicom.sop_class import (
	PatientRootQueryRetrieveInformationModelGet,
	PatientRootQueryRetrieveInformationModelMove,
	PatientRootQueryRetrieveInformationModelFind,
	RTBeamsTreatmentRecordStorage,
	RTPlanStorage
)
from pydicom.dataset import Dataset

fn = os.path.join(os.path.dirname(__file__), 'config/config.toml')
with open(fn, 'rb') as f:
    config = tomllib.load(f)

def c_move_to_krest_hus(patient_id):
	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

	assoc = this_ae.associate(
		config["conquest"]["2"]["server"],
        config["conquest"]["2"]["port"],
        ae_title=config["conquest"]["2"]["aet"]
	)

	if not assoc.is_established:
		raise RuntimeError("Association to MEDFYSHUS-1 failed")

	# Send SOP Series UID for CT
	# Send SOP Instance UID for all others

	ds = Dataset()
	ds.QueryRetrieveLevel = "PATIENT"
	ds.PatientID = patient_id

	responses = assoc.send_c_move(
		ds,
		move_aet=config["krest"]["aet"]
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	assoc.release()

def c_move_to_medfys2(plan_set):
	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

	assoc = this_ae.associate(
		config["conquest"]["1"]["server"],
        config["conquest"]["1"]["port"],
        ae_title=config["conquest"]["1"]["aet"]
	)

	if not assoc.is_established:
		raise RuntimeError("Association to MEDFYSHUS-1 failed")

	# Send SOP Series UID for CT
	# Send SOP Instance UID for all others

	for modality, uid_set in plan_set.items():
		if modality == "PatientID":
			# Bad data model, i know i know
			continue

		if modality == "CT":
			for uid in uid_set:
				ds = Dataset()
				ds.QueryRetrieveLevel = "SERIES"
				ds.SeriesInstanceUID = uid

				responses = assoc.send_c_move(
					ds,
					move_aet="MEDFYSHUS6666-2",
					query_model=PatientRootQueryRetrieveInformationModelMove
				)

		else:
			for uid in uid_set:
				ds = Dataset()
				ds.QueryRetrieveLevel = "IMAGE"
				ds.SOPInstanceUID = uid

				responses = assoc.send_c_move(
					ds,
					move_aet="MEDFYSHUS6666-2",
					query_model=PatientRootQueryRetrieveInformationModelMove
				)
	assoc.release()