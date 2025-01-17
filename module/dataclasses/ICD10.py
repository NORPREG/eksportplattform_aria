from module.dataclasses.custom_exceptions import TerminologyNotFoundException

class ICD10:
    def __init__(self):
        self.ICD10 = dict()
        with open("terminologies/icd10.csv", "r", encoding='utf-8') as csv:
            for line in csv.readlines():
                lineparsed = line.replace("\n", "").split(";")
                self.ICD10[lineparsed[0]] = lineparsed[1]

    def getICD10Definition(self, code: str) -> str:
        if code not in self.ICD10:
            raise TerminologyNotFoundException(f"ICD10 code not found: {code}")

        return self.ICD10.get(code)
