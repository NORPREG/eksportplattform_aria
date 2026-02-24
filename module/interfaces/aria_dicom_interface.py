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

from module.interfaces import aria_db_interface

from pydicom.dataset import Dataset
from dataclass.conquest_dataclass import (
	DICOMPatients,
	DICOMImages,
	DICOMSeries,
	DICOMStudies
)

from sqlmodel import create_engine, Session, select, exists


logger = logging.getLogger(__name__)

fn = os.path.join(os.path.dirname(__file__), 'config/config.toml')
with open(fn, 'rb') as f:
    config = tomllib.load(f)

engine = create_engine(config["aria"]["sql"]["uri"])

def get_assoc():
	ae = AE(ae_title=config["conquest"]["1"]["aet"])
	ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
	ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

	assoc = ae.associate(
		config["aria"]["dicom"]["server"],
		config["aria"]["dicom"]["port"],
		ae_title=config["aria"]["dicom"]["aet"]
	)

	if not assoc.is_established:
		raise RuntimeError("Association to ARIA failed")

	return assoc

def c_move_image(association, uid):
	if conquest_db_interface.check_exists_sop(uid):
		return

	ds = Dataset()
	ds.QueryRetrieveLevel = "IMAGE"
	ds.SOPInstanceUID = uid

	responses = assoc.send_c_move(
		ds,
		move_aet=config["conquest"]["1"]["aet"],
		query_model=PatientRootQueryRetrieveInformationModelMove
	)

	for status, identifier in responses:
		if status:
			pass
		else:
			print("[GET] Connection timed out")

def c_move_series(association, uid):
	if conquest_db_interface.check_exists_series(uid):
		return

	ds = Dataset()
	ds.QueryRetrieveLevel = "SERIES"
	ds.SeriesInstanceUID = uid

	responses = assoc.send_c_move(
		ds,
		move_aet=config["conquest"]["1"]["aet"],
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