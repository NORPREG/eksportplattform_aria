import hashlib
import logging
from configparser import ConfigParser
import shlex
import subprocess

from module.dataclasses.conquest_dataclass import (
	DICOMImages, 
	DICOMPatients,
)
from sqlmodel import select

from config import Config
from pathlib import Path

config = Config()

logger = logging.getLogger(__name__ + f" (config.HF)")

"""
Interface code for interacting with the Conquest DATABASE.
It is also possible to speak DICOM with Conquest, but it's
far easier to access the database directly.
The config object contains the authentication information.

In addition, some of the function use the dgate.exe
executable, e.g. to move studies from staging to registry.
"""


def get_conquest_data_dir():
	ini_file = config.conquest.stg.app_dir / "dicom.ini"
	parsed_ini = ConfigParser()
	parsed_ini.read(ini_file)

	# The SSCSCP section is the only one defined in the .ini
	# Although the file itself should be sectioned better
	data_dir = Path(parsed_ini['sscscp']['MAGDevice0'])

	return data_dir

def get_conquest_database_file():
	ini_file = config.conquest.stg.app_dir / "dicom.ini"
	print(ini_file)
	parsed_ini = ConfigParser()
	parsed_ini.read(ini_file)

	print(parsed_ini)

	db_file = Path(parsed_ini['sscscp']['SQLServer'])
	return db_file

def fetch_patients_from_conquest(session) -> DICOMPatients:
	statement = select(DICOMPatients)
	try:
		results = session.exec(statement)
		return results
	except Exception as e:
		logging.error(f"Error in fetching patients from the Staging Conquest: {e}")
		return DICOMPatients()


def fetch_study_uids_from_conquest(patient) -> list:
	UIDs = set()
	for study in patient.studies:
		UIDs.add(study.StudyInstanceUID)
	return list(UIDs)


def fetch_series_uids_from_conquest(patient) -> list:
	UIDs = set()
	for study in patient.studies:
		for series in study.series:
			UIDs.add(series.SeriesInstanceUID)
	return list(UIDs)


def calculate_md5sum(session, series_uid=None, patient=None) -> str:
	data_dir = get_conquest_data_dir()
	
	if patient:
		files = fetch_file_list(session, patient=patient)
	elif series_uid:
		files = fetch_file_list(session, series_uid=series_uid)
	else:
		files = fetch_file_list(session)
	data = b''
	for file in files:
		with open(data_dir + file, 'rb') as file_to_check:
			data += file_to_check.read()

	md5 = hashlib.md5(data).hexdigest()

	logging.info(f"The md5sum of the whole DICOM dataset is {md5}.")

	return md5


def fetch_file_list(session, series_uid=None, patient=None) -> list:
	if series_uid:
		statement = select(DICOMImages).where(DICOMImages.SeriesInst == series_uid)
	elif patient:
		statement = select(DICOMImages).where(DICOMImages.ImagePat == patient.PatientID)
	else:
		statement = select(DICOMImages)
	results = session.exec(statement)
	file_list = list()
	for file_object in results:
		file_list.append(file_object.ObjectFile)

	return sorted(file_list)

def get_file_tree(patient: DICOMPatients) -> dict():	
	supported_modalities = ['CT', 'MR', 'RTPLAN', 'RTDOSE', 'RTSTRUCT', 'RTRECORD']
	modalities = set()
	basepath = get_conquest_data_dir()

	file_tree = { k: list() for k in supported_modalities }
	unsupported_modalities = set()

	for study in patient.studies:
		for series in study.series:
			modalities.add(series.Modality)
			if series.Modality not in file_tree:
				unsupported_modalities.add(series.Modality)
				# logging.warning(f"Modality not supported: {series.Modality}")
				continue
	
			for image in series.images:			
				file_tree[series.Modality].append(basepath / image.ObjectFile)

	if len(unsupported_modalities):
		mod_list = ",".join(list(unsupported_modalities))
		logging.warning(f"Modalities not supported: {mod_list}")

	return file_tree

def move_to_registry(pat_id):
	"""Run dgate.exe to move patient to registry Conquest

		dgate64 --movepatient:source_aet,dest_aet,pat_id"""
		
	executable = config.conquest.stg.app_exe
	source_aet = config.conquest.stg.aet
	dest_aet = config.conquest.reg.aet

	if not pat_id.isalnum():
		logger.error(f"Invalid input: Patient ID must be alphanumeric for patient {pat_id}")
		raise ValueError("Invalid input: Patient ID must be alphanumeric")

	pat_id_safe = shlex.quote(pat_id)

	if pat_id_safe != pat_id:
		"""Should never happen due to isalnum, but still a failsafe"""

		logger.error(f"Dangerous patient_id according to shlex: {pat_id}")
		return

	command_to_run = [
		executable, 
		f"--movepatient:{source_aet},{dest_aet},{pat_id_safe}"
	]

	try:
		subprocess.run(command_to_run, check=True)
		logging.info("Successfully moved {pat_id} from {source_aet} to {dest_aet}")

	except subprocess.CalledProcessError as e:
		logging.error(f"Error executing command: {e}")


def delete_from_staging(pat_id):
	"""Run dgate.exe to move patient to registry Conquest

		dgate64 --movepatient:source_aet,dest_aet,pat_id"""
		
	executable = config.conquest.stg.app_exe
	source_aet = config.conquest.stg.aet

	if not pat_id.isalnum():
		logger.error(f"Invalid input: Patient ID must be alphanumeric for patient {pat_id}")
		raise ValueError("Invalid input: Patient ID must be alphanumeric")

	pat_id_safe = shlex.quote(pat_id)

	if pat_id_safe != pat_id:
		"""Should never happen due to isalnum, but still a failsafe"""

		logger.error(f"Dangerous patient_id according to shlex: {pat_id}")
		return

	command_to_run = [
		executable, 
		f"--deletepatient:{pat_id_safe}"
	]

	try:
		subprocess.run(command_to_run, check=True)
		logging.info("Successfully deleted {pat_id} from {source_aet}")

	except subprocess.CalledProcessError as e:
		logging.error(f"Error executing command: {e}")