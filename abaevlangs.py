import csv
import sys
from dataclasses import dataclass

@dataclass
class AbaevLang:
    code: str
    glottocode: str
    name_ru: str
    name_en: str
    comment: str
    latitude: str
    longitude: str
    @classmethod
    def from_dict(cls,input: dict):
        return cls(code = input["code"], 
         glottocode = input["glottolog"], 
         name_ru = input["ru"],
         name_en = input["en"], 
         comment = input["comment"],
         latitude = input["lat"],
         longitude = input["long"])

    def asdict(self):
        return {"code": self.code, 
        "glottolog": self.glottocode, 
        "ru": self.name_ru,
        "en": self.name_en,
        "comment": self.comment,
        "lat": self.latitude,
        "long": self.longitude}

class AbaevLangDict(dict):
    @classmethod
    def from_csv(cls,filename: str):
        dict = cls()
        with open(filename) as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                code = row["code"]
                dict[code] = AbaevLang.from_dict(row)
        return dict

    def __setitem__(self, key, value):
        if not isinstance(value, AbaevLang):
            raise TypeError(repr(type(value)))
        super(AbaevLangDict,self).__setitem__(key, value)

    def write_csv(self, file):
        with file as csv_file:
            fieldnames = list(AbaevLang().asdict().keys())
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=',')
            csv_writer.writeheader()
            for key in sorted(self.keys()):
                csv_writer.writerow(self[key].asdict())