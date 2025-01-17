from module.dataclasses.custom_exceptions import TerminologyNotFoundException

class NKPK:
    def __init__(self):
        self.NKPK = dict()
        with open("terminologies/prosedyrekoder.csv", "r", encoding='utf-8') as csv:
            for line in csv.readlines():
                lineparsed = line.split(";")
                self.NKPK[lineparsed[0]] = lineparsed[1].replace("\n", "")

    def getNKPKDefinition(self, code: str) -> str:
        if code not in self.NKPK:
            raise TerminologyNotFoundException(f"NKPK code not found: {code}")

        return self.NKPK.get(code)
