from __future__ import annotations
import csv
import sys
from dataclasses import dataclass
from enum import Enum,auto
from lxml import etree

@dataclass
class Language:
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

class LanguageDict(dict):
    @classmethod
    def from_csv(cls,filename: str):
        dict = cls()
        with open(filename) as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                code = row["code"]
                dict[code] = Language.from_dict(row)
        return dict

    def __setitem__(self, key, value):
        if not isinstance(value, Language):
            raise TypeError(repr(type(value)))
        super(LanguageDict,self).__setitem__(key, value)

    def write_csv(self, file):
        with file as csv_file:
            fieldnames = list(list(self.values())[1].asdict().keys())
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=',')
            csv_writer.writeheader()
            for key in sorted(self.keys()):
                csv_writer.writerow(self[key].asdict())

class FormType(Enum):
    LEXICAL = auto()
    SENTENCE = auto()
    CLAUSE = auto()
    WORD = auto()
    MORPHEME = auto()
    PHONETIC = auto()


@dataclass
class Form:
    content: str
    lang: Language
    participle: Form = None
    '''Participles are a feature of lexical forms (in lexical entries)'''
    variants: list[Form] = None
    '''Variants are a feature of lexical forms (in lexical entries)'''

@dataclass
class Sense:
    text: str
    is_def: bool = False
    sub_senses: list[Sense] = None
    number: int = None

@dataclass
class Example:
    text: str
    lang: Language
    tr: str

@dataclass
class ExampleGroup:
    examples: list[Example]
    number: int = None

@dataclass
class Mentioned:
    forms: array(Form)
    lang: Language
    glosses: list[str]

@dataclass
class Etymology:
    mentioned_forms: list[Mentioned]

@dataclass
class Entry:
    id: InitVar[str]
    lang: Language
    lemma: Form
    digorForm: Form = None
    senses: list[Sense] = None
    example_groups: list[ExampleGroup] = None
    related_entries: list[Entry] = None
    mentioned_forms: list[Mentioned] = None

def get_forms(element: lxml.etree._Element, type: str, langs: LanguageDict, namespaces: dict) -> list[Form]:
    forms = [] # type: list[Form]
    for node in element.xpath("tei:form[@type='" + type + "']",namespaces=namespaces):
        content = node.xpath("tei:orth/text()",namespaces = namespaces)[0]
        lang = langs[node.xpath("ancestor-or-self::*[@xml:lang][1]/@xml:lang",namespaces=namespaces)[0]]
        ptcps = get_forms(node, type = "participle", langs = langs, namespaces = namespaces)
        variants = get_forms(node, type = "participle", langs = langs, namespaces = namespaces)
        form = Form(content=content, lang=lang, participle=ptcps[0] if ptcps else None, variants=variants if variants else None)
        forms.append(form)
    return forms

langdata = LanguageDict.from_csv("../abaev-tei-oxygen/css/langnames.csv")
entry_file = open("../abaevdict-tei/entries/abaev_līʒyn.xml","r")
tree = etree.parse(entry_file)
entry_file.close()
namespaces = {"tei": "http://www.tei-c.org/ns/1.0", "abv":"http://ossetic-studies.org/ns/abaevdict"}
entry = tree.xpath("//tei:entry",namespaces=namespaces)[0]
lemma = get_forms(element = entry, type = "dialectal", langs = langdata, namespaces = namespaces)
print(lemma)