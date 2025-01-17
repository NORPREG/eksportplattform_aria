# eksportplattform_aria

1. Use `module/sync_aria.py` to connect to the Aria DB to fetch list of DICOM UIDs of recently finished RT patients. Store these UIDs in the `patient_list` sqlite DB
2. Use `module/sync_conquest.py` to connect to the Aria DICOM DB to fetch DICOM series having UIDs matching those in the `patient_list`. The `dgate.exe` interface is used here, e.g. with `dgate.exe --moveseries:aria_aet,conquest_aet,seriesUID`.
3. Use `module/import_npr.py` to connect with the relevant DB and import additional NPR data for the patient. Embed these in DICOM SR/XML. Add to patient in Conquest with same Study UID / Course ID etc.
3. Use `module/export_krest.py` to send the DICOM package to the KREST-HUS registry.

All the relevant configuration is performed in `config/config.toml`. The `dataclass` folder contains the Pydantic / SQL Model dataclasses for ORM integration. The `interface` folder contains the interface code towards Aria, NPR and Conquest.