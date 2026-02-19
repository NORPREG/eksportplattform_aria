from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from typing import List
import pyodbc
import logging
from pprint import pprint
import os
from datetime import datetime

logging.basicConfig(
	filename="../../export.log", 
	filemode='a', 
	format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	level=logging.INFO)


logger = logging.getLogger(__name__)

# Aria SQL Interface

def get_sqlalchemy():
	conn_string = "mssql+pyodbc://VIR-APP5338/VARIAN?driver=SQL+Server"
	engine = create_engine(conn_string)
	return engine

def blp_GetTxRecordsProtonToExport(from_dt: datetime = None) -> List[TxRecordsProtonToExport]:
	engine_varian = get_sqlalchemy()

	if from_dt:
		from_str = from_dt.strftime("%Y%m%d")

	with engine_varian.connect() as conn:
		if from_str:
			result = conn.execute(text("SET NOCOUNT ON; EXEC blp_GetTxRecordsProtonToExport @FromDateTime = :from_datetime"), 
				{"from_datetime": dt})
		else:
			result = conn.execute(text("SET NOCOUNT ON; EXEC blp_GetTxRecordsProtonToExport"))
		rows = result.mappings().all()

		return [TxRecordsProtonToExport(**dict(row)) for row in rows]

def find_rtplans_from_sql():
	rtrecords = blp_GetTxRecordsProtonToExport()
	plan_set = dict()

	for rtrecord in rtrecords:
		if not rtrecord.PatientSer in plan_set:
			plan_set[rtrecord.PatientSer] = {
				"PatientID": None,
				"RTPLAN": set(),
				"RTPlanLabel": set(),
				"RTRECORD": set(),
				"RTSTRUCT": set(),
				"RTDOSE": set(),
				"CT": set()
			}
		
		plan_set[rtrecord.PatientSer]["RTPLAN"].add(rtrecord.PlanUID)
		plan_set[rtrecord.PatientSer]["RTRECORD"].add(rtrecord.TreatmentRecordUID)

	return plan_set
