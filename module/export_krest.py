# Send files from Conquest to registry

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from typing import List
import pyodbc
import json
import logging
from pprint import pprint
import subprocess
import os
from glob import glob
import pydicom
import datetime

from pynetdicom import AE, evt, build_role, debug_logger
from pynetdicom.sop_class import (
	PatientRootQueryRetrieveInformationModelGet,
	PatientRootQueryRetrieveInformationModelMove,
	PatientRootQueryRetrieveInformationModelFind,
	RTBeamsTreatmentRecordStorage,
	RTPlanStorage
)

from pydicom.dataset import Dataset
from dataclass.conquest_dataclass import (
	DICOMPatients,
	DICOMImages,
	DICOMSeries,
	DICOMStudies
)

from sqlmodel import create_engine, Session, select, exists

ROOT_DIR = "D:/Conquest/MEDFYSHUS6666-1/data/"

logging.basicConfig(
	filename="../export.log", 
	filemode='a', 
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	level=logging.INFO)


logger = logging.getLogger(__name__)

# debug_logger()


# Didivde into the following

# Config singleton (DON'T bother about datamodel)
# Conquest SQL Interface | Datamodel
# Conquest PACS Interface
# Aria PACS Interface
# Aria SQL Interface | Datamodel 
# Logger Database SQL Interface | Datamodel


# Logger Database SQL Interface | Datamodel

# CONFIG

login = f"root:BestefarKjeksKaffe"
mysql_uri = f"mysql+pymysql://{login}@localhost/conquest_1"
engine = create_engine(mysql_uri)

output_dicom = "data/pynetdicom/"
this_aet = "MEDFYSHUS6666-1"
aria_aet = "VMSDBD"
aria_port = 57347
aria_server = "VIR-APP5340"

medfys1_port = 57863
medfys1_server = "127.0.0.1"
medfys2_port = 31416
medfys2_server = "127.0.0.1"

# General PACS interface
ae = AE(ae_title=this_aet)
ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

# Conquest PACS Interface

def c_move_to_medfys2(plan_set):
	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

	assoc = this_ae.associate(
		medfys1_server,
		medfys1_port,
		ae_title="MEDFYSHUS6666-1"
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



def c_move_to_krest_hus(patient_id):
	this_ae = AE(ae_title="PYTHON")
	this_ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

	assoc = this_ae.associate(
		medfys2_server,
		medfys2_port,
		ae_title="MEDFYSHUS6666-2"
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
		move_aet="GW_HUS",
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	assoc.release()


# Aria PACS Interface

def get_assoc():
	assoc = ae.associate(
		aria_server,
		aria_port,
		ae_title=aria_aet,
	)

	if not assoc.is_established:
		raise RuntimeError("Association to ARIA failed")

	return assoc

def c_move_image(association, uid):
	with Session(engine) as session:
		statement = select(DICOMImages).where(DICOMImages.SOPInstanceUID == uid)
		result = session.exec(statement)
		if result.first() is not None:
			# found c_move_image in Conquest, skipping
			return

	ds = Dataset()
	ds.QueryRetrieveLevel = "IMAGE"
	ds.SOPInstanceUID = uid

	responses = assoc.send_c_move(
		ds,
		move_aet="MEDFYSHUS6666-1",
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	for status, identifier in responses:
		if status:
			pass
		else:
			print("[GET] Connection timed out")

def c_move_series(association, uid):
	with Session(engine) as session:
		statement = select(DICOMSeries).where(DICOMSeries.SeriesInstanceUID == uid)
		result = session.exec(statement)
		if result.first() is not None:
			# Found c_move_series in Conquest, skipping...
			return

	ds = Dataset()
	ds.QueryRetrieveLevel = "SERIES"
	ds.SeriesInstanceUID = uid

	responses = assoc.send_c_move(
		ds,
		move_aet="MEDFYSHUS6666-1",
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	for status, identifier in responses:
		if status:
			pass
		else:
			print("[GET] Connection timed out")

def c_find_study(association, uid):
	ds = Dataset()
	ds.QueryRetrieveLevel = "SERIES"
	ds.StudyInstanceUID = uid
	ds.SeriesInstanceUID = ""
	ds.Modality = ""

	result = list()

	responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)

	for status, identifier in responses:
		if status and status.Status in (0xFF00, 0xFF01):

			result.append({
				"SeriesInstanceUID": identifier.get("SeriesInstanceUID"),
				"StudyInstanceUID": identifier.get("StudyInstanceUID"),
				"Modality": identifier.get("Modality"),
			})

	return result

def get_study_uid_from_plan_sop_uid(assoc, plan_sop_uid):
	ds = Dataset()
	ds.QueryRetrieveLevel = "IMAGE"
	ds.SOPInstanceUID = plan_sop_uid
	ds.StudyInstanceUID = ""
	ds.SeriesInstanceUID = ""
	ds.Modality = ""

	result = list()

	responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)

	for status, identifier in responses:
		if status and status.Status in (0xFF00, 0xFF01):

			result.append({
				"StudyInstanceUID": identifier.get("StudyInstanceUID"),
				"SOPInstanceUID": identifier.get("SOPInstanceUID"),
				"SeriesInstanceUID": identifier.get("SeriesInstanceUID"),
				"Modality": identifier.get("Modality"),
			})

	return result