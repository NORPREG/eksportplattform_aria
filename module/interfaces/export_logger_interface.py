# MOVE THIS TO MSSQL

class LogDatabase:
	def __init__(self):
		self.log = self.get_log()

	def get_log(self):
		try:
			with open("patient_log.json", "r", encoding="utf-8") as input_file:
				d =  json.load(input_file)
				print(f"Found {len(d)} patients in patient_log.json.")
				return d
		except:
			return list()

	def save(self):
		with open("patient_log.json", "w", encoding="utf-8") as output_file:
			json.dump(self.log, output_file, indent=3)
		
 
	def add_patient(self, patient_ser, plan_set: dict):
		new_entry = {
			"sent_dt": datetime.datetime.now().isoformat(),
			"patient_ser": patient_ser,
			"plan_set": { k:list(v) for k,v in plan_set.items() if k != "PatientID"}
		}
		self.log.append(new_entry)


	def check_patient(self, patient_ser: str) -> bool:
		for entry in self.log:
			if entry.get("patient_ser") == patient_ser:
				return entry.get("sent_dt")
		return False

	@property
	def plan_set(self):
		return self.log
