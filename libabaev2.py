from __future__ import annotations
# import os
import csv
# import sys
from dataclasses import dataclass, fields, asdict
from enum import Enum
from lxml import etree
from typing import *

NAMESPACES = {"tei": "http://www.tei-c.org/ns/1.0", "abv": "http://ossetic-studies.org/ns/abaevdict"}


class DataClassUnpack:
    classFieldCache = {}

    @classmethod
    def instantiate(cls, class_to_instantiate, arg_dict):
        if class_to_instantiate not in cls.classFieldCache:
            cls.classFieldCache[class_to_instantiate] = {f.name for f in fields(class_to_instantiate) if f.init}

        field_set = cls.classFieldCache[class_to_instantiate]
        filtered_arg_dict = {k: v for k, v in arg_dict.items() if k in field_set}
        return class_to_instantiate(**filtered_arg_dict)


def normalize(string: str) -> str:
    return " ".join(string.split())


@dataclass
class Language:
    code: str
    glottocode: str
    name_ru: str
    name_en: str
    comment: str
    latitude: float = 0.0
    longitude: float = 0.0


class LanguageDict(Dict[str, Language]):
    @classmethod
    def from_csv(cls, filename: str):
        lang_dict = cls()
        with open(filename) as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                for key in row:
                    if row[key] == '':
                        row[key] = None
                code = row["code"]
                lang_dict[code] = Language(code=code,
                                           glottocode=row["glottolog"],
                                           name_ru=row["ru"],
                                           name_en=row["en"],
                                           comment=row["comment"])
                if row["lat"]:
                    lang_dict[code].latitude = float(row["lat"])
                if row["long"]:
                    lang_dict[code].longitude = float(row["long"])
        return dict

    def write_csv(self, file):
        with file as csv_file:
            # fieldnames = list(list(self.values())[1].asdict().keys())
            fieldnames = ["code", "glottolog", "ru", "en", "comment", "lat", "long"]
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=',')
            csv_writer.writeheader()
            for key in sorted(self.keys()):
                row = {"code": key, "glottolog": self[key].glottocode, "ru": self[key].name_ru,
                       "en": self[key].name_en, "comment": self[key].comment, "lat": self[key].latitude,
                       "long": self[key].longitude}
                csv_writer.writerow(row)


@dataclass
class Entry:
    db_id: str  # Equivalent to the XML id
    lemma: str
    lang: str = None  # Language ID, can be none in subentries
    num: int = None
    main_entry: str = None  # Main entry if this is a subentry, otherwise None


def get_entry(node: etree.ElementBase) -> Entry:
    entry = Entry(db_id=node.xpath("@xml:id", namespaces=NAMESPACES)[0],
                  lemma=normalize(node.xpath("string(tei:form[@type='lemma']/tei:orth)", namespaces=NAMESPACES)))
    lang_node = node.xpath("@xml:lang", namespaces=NAMESPACES)
    if len(lang_node) > 0:
        entry.lang = lang_node[0]
    num_node = node.xpath("@n", namespaces=NAMESPACES)
    if len(num_node) > 0:
        entry.num = num_node[0]
    return entry


EntryDict = dict[str, Entry]


def get_entries_from_csv(filename: str) -> EntryDict:
    entry_dict = EntryDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            if row["num"] == '':
                row["num"] = None
            else:
                row["num"] = int(row["num"])
            entry_dict[row["db_id"]] = DataClassUnpack.instantiate(Entry, row)
    return entry_dict


class FormRelType(Enum):
    VARIANT = "variant"
    PARTICIPLE = "participle"


@dataclass
class Form:
    db_id: str  # Should be same as XML id because forms are never unified
    entry_id: str  # ID of the entry to which the form belongs
    orth: str
    lang: str  # Language ID
    rel_of: str = None  # If variant or participle of something, ID here
    rel_type: FormRelType = None  # Type of variant or participle


FormDict = dict[str, Form]


def get_forms(node: etree.ElementBase, entry_id: str, form_id: str = None) -> FormDict:
    form_dict = FormDict()
    for form_node in node.xpath("tei:form", namespaces=NAMESPACES):
        form = Form(db_id=form_node.xpath("@xml:id", namespaces=NAMESPACES)[0],
                    entry_id=entry_id,
                    orth=form_node.xpath("string(tei:orth)", namespaces=NAMESPACES),
                    lang=form_node.xpath("ancestor-or-self::*[@xml:lang][1]/@xml:lang", namespaces=NAMESPACES)[0])

        if form_id:
            form.rel_of = form_id
            if form_node.xpath("@type", namespaces=NAMESPACES)[0] == 'variant':
                form.rel_type = FormRelType.VARIANT
            elif form_node.xpath("@type", namespaces=NAMESPACES)[0] == 'participle':
                form.rel_type = FormRelType.PARTICIPLE
        form_dict[form.db_id] = form
        form_dict = form_dict | get_forms(node=form_node, entry_id=entry_id, form_id=form.db_id)
    return form_dict


def get_forms_from_csv(filename: str) -> FormDict:
    form_dict = FormDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            for key in row:
                if row[key] == '':
                    row[key] = None
            if row["rel_type"]:
                row["rel_type"] = FormRelType(row["rel_type"])
            form_dict[row["db_id"]] = DataClassUnpack.instantiate(Form, row)
    return form_dict


# Only bottom-level senses are treated as actual senses. Sense 'groups' are viewed as IDs that are attached to
# individual senses. These are stored as dictionaries that map the sense group ID to entry ID
@dataclass
class Sense:
    db_id: str  # Should be the same as XML id
    entry_id: str  # db_id of the entry
    description_ru: str
    description_en: str
    lang: str = None  # Language ID, if sense has one
    is_def: bool = False  # True if this is a definition, not translation in quotes
    sense_group: str = None  # ID of the sense group that this belongs to
    num: int = None  # If group has a number


SenseDict = dict[str, Sense]


def get_senses_from_csv(filename: str) -> SenseDict:
    sense_dict = SenseDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            for key in row:
                if row[key] == '':
                    row[key] = None
            if row["is_def"] == "1":
                row["is_def"] = True
            if row["is_def"] == "0":
                row["is_def"] = False
            if row["num"]:
                row["num"] = int(row["num"])
            sense_dict[row["db_id"]] = DataClassUnpack.instantiate(Sense, row)
    return sense_dict


@dataclass
class SenseGroup:
    db_id: str  # Should be the same as XML id
    entry_id: str  # db_id of the entry
    num: int = None  # if it has a number


SenseGroupDict = dict[str, SenseGroup]


def get_sense_groups_from_csv(filename: str) -> SenseGroupDict:
    sense_group_dict = SenseGroupDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            for key in row:
                if row[key] == '':
                    row[key] = None
            if row["num"]:
                row["num"] = int(row["num"])
            sense_group_dict[row["db_id"]] = DataClassUnpack.instantiate(SenseGroup, row)
    return sense_group_dict


def sense_from_node(db_id: str,
                    node: etree.ElementBase,
                    entry_id: str,
                    lang: str,
                    num: int,
                    group_id: str = None) -> Sense:
    desc_ru = node.xpath("string(tei:def[@xml:lang='ru'])", namespaces=NAMESPACES)
    is_def = False
    if desc_ru != '':
        is_def = True
        desc_en = node.xpath("string(tei:def[@xml:lang='en'])", namespaces=NAMESPACES)
    else:
        desc_ru = node.xpath("string(abv:tr[@xml:lang='ru']/tei:q)", namespaces=NAMESPACES)
        desc_en = node.xpath("string(abv:tr[@xml:lang='en']/tei:q)", namespaces=NAMESPACES)

    sense = Sense(db_id=db_id,
                  entry_id=entry_id,
                  sense_group=group_id,
                  lang=lang,
                  num=num,
                  is_def=is_def,
                  description_ru=normalize(desc_ru),
                  description_en=normalize(desc_en))
    return sense


def get_senses(node: etree.ElementBase, entry_id: str) -> Tuple[SenseDict, SenseGroupDict]:
    sense_dict = SenseDict()
    sense_group_dict = SenseGroupDict()
    for sense_node in node.xpath("tei:sense[descendant::abv:tr or descendant::tei:def]", namespaces=NAMESPACES):
        if normalize(etree.tostring(sense_node, method='text', encoding="unicode")) != '':
            lang = None
            lang_supersense = sense_node.xpath("@xml:lang", namespaces=NAMESPACES)
            if len(lang_supersense) > 0:
                lang = lang_supersense[0]
            num = None
            num_supersense = sense_node.xpath("@n", namespaces=NAMESPACES)
            if len(num_supersense) > 0:
                num = int(num_supersense[0])
            subsenses = sense_node.xpath("tei:sense", namespaces=NAMESPACES)
            if len(subsenses) > 0:
                group_id = sense_node.xpath("@xml:id", namespaces=NAMESPACES)[0]
                sense_group = SenseGroup(db_id=group_id,
                                         entry_id=entry_id,
                                         num=num)
                sense_group_dict[sense_group.db_id] = sense_group
                for subsense_node in subsenses:
                    lang_subsense = subsense_node.xpath("@xml:lang", namespaces=NAMESPACES)
                    if len(lang_subsense) > 0:
                        lang = lang_subsense[0]

                    db_id = subsense_node.xpath("@xml:id", namespaces=NAMESPACES)[0]
                    sense_dict[db_id] = sense_from_node(db_id=db_id,
                                                        node=subsense_node,
                                                        entry_id=entry_id,
                                                        group_id=group_id,
                                                        lang=lang,
                                                        num=num)
            else:
                db_id = sense_node.xpath("@xml:id", namespaces=NAMESPACES)[0]
                sense_dict[db_id] = sense_from_node(db_id=db_id,
                                                    node=sense_node,
                                                    entry_id=entry_id,
                                                    lang=lang,
                                                    num=num)
    return sense_dict, sense_group_dict


# Same mechanism for example groups as for sense groups
@dataclass
class Example:
    db_id: str  # Should be the same as XML id
    entry_id: str  # db_id of the entry
    example_group: str  # Reference to the ID of the group this is part of
    text: str
    tr_ru: str
    tr_en: str
    num: int = None
    lang: str = None  # Language ID


ExampleDict = dict[str, Example]


def get_examples_from_csv(filename: str) -> ExampleDict:
    example_dict = ExampleDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            for key in row:
                if row[key] == '':
                    row[key] = None
            if row["num"]:
                row["num"] = int(row["num"])
            example_dict[row["db_id"]] = DataClassUnpack.instantiate(Example, row)
    return example_dict


@dataclass
class ExampleGroup:
    db_id: str  # Should be the same as XML id
    entry_id: str  # db_id of the entry
    num: int = None


ExampleGroupDict = dict[str, ExampleGroup]


def get_example_groups_from_csv(filename: str) -> ExampleGroupDict:
    example_group_dict = ExampleGroupDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            for key in row:
                if row[key] == '':
                    row[key] = None
            if row["num"]:
                row["num"] = int(row["num"])
            example_group_dict[row["db_id"]] = DataClassUnpack.instantiate(ExampleGroup, row)
    return example_group_dict


def get_examples(node: etree.ElementBase, entry_id: str) -> Tuple[ExampleDict, ExampleGroupDict]:
    example_dict = ExampleDict()
    example_group_dict = ExampleGroupDict()
    for group_node in node.xpath("abv:exampleGrp", namespaces=NAMESPACES):
        group_id = group_node.xpath("@xml:id", namespaces=NAMESPACES)[0]
        group = ExampleGroup(db_id=group_id,
                             entry_id=entry_id)

        num = None
        num_group = group_node.xpath("@n", namespaces=NAMESPACES)
        if len(num_group) > 0:
            num = int(num_group[0])
            group.num = num

        example_group_dict[group_id] = group

        examples = group_node.xpath("abv:example[not(@xml:lang='ru')]", namespaces=NAMESPACES)
        for example_node in examples:
            extext = example_node.xpath("tei:quote", namespaces=NAMESPACES)[0]
            if extext.text is not None:
                db_id = example_node.xpath("@xml:id", namespaces=NAMESPACES)[0]
                example = Example(db_id=db_id,
                                  entry_id=entry_id,
                                  example_group=group_id,
                                  num=num,
                                  text=normalize(extext.xpath("string()", namespaces=NAMESPACES)),
                                  tr_ru=normalize(example_node.xpath("string(abv:tr[@xml:lang='ru']/tei:q)",
                                                                     namespaces=NAMESPACES)),
                                  tr_en=normalize(example_node.xpath("string(abv:tr[@xml:lang='en']/tei:q)",
                                                                     namespaces=NAMESPACES)))

                lang_example = example_node.xpath("@xml:lang", namespaces=NAMESPACES)
                if len(lang_example) > 0:
                    example.lang = lang_example[0]

                example_dict[db_id] = example
    return example_dict, example_group_dict


@dataclass
class Mentioned:
    db_id: str  # Not necessarily the same as XML id (if several are unified into one)
    xml_id: list[str]  # List of equivalent XML ids
    entry_id: str  # Entry or entries in which this mentioned form appears
    langs: list[str]  # Language ID
    form: list[str]  # May include multiple words
    gloss_ru: list[str]  # May include multiple glosses
    gloss_en: list[str]  # May include multiple glosses
    same_as: str = None  # If equivalent to another entry


MentionedDict = dict[str, Mentioned]


def get_mentioneds_from_csv(filename: str) -> MentionedDict:
    mentioned_dict = MentionedDict()
    with open(filename, "r") as file:
        csv_reader = csv.DictReader(file, delimiter=",")
        for row in csv_reader:
            for key in row:
                if row[key] == '':
                    row[key] = None
            for val in ["xml_id", "langs", "form", "gloss_ru", "gloss_en"]:
                if row[val]:
                    if ',' in row[val]:
                        row[val] = row[val].split(",")
                    else:
                        row[val] = [row[val]]
            mentioned_dict[row["db_id"]] = DataClassUnpack.instantiate(Mentioned, row)
    return mentioned_dict


word_elem = "*[name() = 'w' or name() = 'm' or name() = 'cl' or name() = 'phr' or name() = 's']"


def get_mentioned(node: etree.ElementBase, entry_id: str, english: bool = False) -> Mentioned:
    words = node.xpath(word_elem + "[text()]", namespaces=NAMESPACES)
    if len(words) > 0:
        node_id = str(node.xpath("@xml:id", namespaces=NAMESPACES)[0])
        xml_id = [node_id]

        # Make list of languages
        langs = node.xpath("@xml:lang", namespaces=NAMESPACES)
        extralang = node.xpath("@extralang", namespaces=NAMESPACES)
        if len(extralang) > 0:
            langs = langs + extralang[0].split()

        # Make list of forms
        forms = []
        for node_w in words:
            w = normalize(node_w.xpath("string()", namespaces=NAMESPACES))
            if node_w.xpath("@type = 'rec'", namespaces=NAMESPACES):
                w = '*' + w
            forms.append(w)

        glosses_ru = []

        if not english:
            # Make list of Russian glosses
            for gloss_node in node.xpath("tei:gloss", namespaces=NAMESPACES):
                quoted_nodes = gloss_node.xpath("tei:q", namespaces=NAMESPACES)
                if len(quoted_nodes) > 0:
                    for quote in quoted_nodes:
                        glosses_ru.append(normalize(quote.xpath("string()", namespaces=NAMESPACES)))
                else:
                    gloss_text = gloss_node.xpath("string()", namespaces=NAMESPACES)
                    if gloss_text != '':
                        glosses_ru.append(normalize(gloss_text))

            # Find reference to corresponding English node            en_id = None
            node_en = None
            corresp = node.xpath("@corresp", namespaces=NAMESPACES)
            if len(corresp) > 0:
                en_id = corresp[0][1:]
                node_en = node.xpath("//tei:mentioned[@xml:id='" + en_id + "']", namespaces=NAMESPACES)[0]
                xml_id.append(en_id)
        else:
            node_en = node

        # Make list of English glosses
        glosses_en = []
        if node_en is not None:
            for gloss_node in node_en.xpath("tei:gloss", namespaces=NAMESPACES):
                quoted_nodes = gloss_node.xpath("tei:q", namespaces=NAMESPACES)
                if len(quoted_nodes) > 0:
                    for quote in quoted_nodes:
                        glosses_en.append(normalize(quote.xpath("string()", namespaces=NAMESPACES)))
                else:
                    gloss_text = gloss_node.xpath("string()", namespaces=NAMESPACES)
                    if gloss_text != '':
                        glosses_en.append(normalize(gloss_text))

        return Mentioned(db_id=node_id,
                         xml_id=xml_id,
                         entry_id=entry_id,
                         langs=langs,
                         form=forms,
                         gloss_ru=glosses_ru,
                         gloss_en=glosses_en)


def get_mentioneds(node: etree.ElementBase, entry_id: str) -> MentionedDict:
    mentioned_dict = MentionedDict()
    for node_m in node.xpath("//tei:etym[@xml:lang='ru']//tei:mentioned", namespaces=NAMESPACES):
        mentioned = get_mentioned(node=node_m,
                                  entry_id=entry_id)
        if mentioned:
            mentioned_dict[mentioned.db_id] = mentioned
    for node_m in node.xpath("//tei:etym[@xml:lang='en']//tei:mentioned[not(@corresp)]", namespaces=NAMESPACES):
        mentioned = get_mentioned(node=node_m,
                                  entry_id=entry_id,
                                  english=True)
        if mentioned:
            mentioned_dict[mentioned.db_id] = mentioned
    return mentioned_dict


def abaev_key(x):
    x = x.replace('entry_', '')
    # print (x)

    # Remove initial punctuation which does not influence order
    if x[0] == '7' or x[0] == '-' or x[0] == '8' or x[0] == '6':
        x = x[1:]

    # Remove word-internal punctuation and accent marks (a bit redundant but let it be)
    x = x.replace('6', '')
    x = x.replace('9', '')
    x = x.replace('-', '')
    x = x.replace('_', '')
    x = x.replace('́', '')  # combining acute
    x = x.replace('1', '')
    x = x.replace('2', '')
    x = x.replace('3', '')
    x = x.replace('4', '')
    x = x.replace('5', '')

    x = x.replace('a', '/')
    x = x.replace('A', '/')
    x = x.replace('ā', '/')
    x = x.replace('Ā', '/')
    x = x.replace('á', '/')
    x = x.replace('Á', '/')
    x = x.replace('ā́', '/')
    x = x.replace('Ā́', '/')

    x = x.replace('æ', '1')
    x = x.replace('Æ', '1')
    x = x.replace('ǽ', '1')
    x = x.replace('Ǽ', '1')

    x = x.replace('b', '2')
    x = x.replace('B', '2')

    x = x.replace('cʼ', '4')
    x = x.replace('Cʼ', '4')

    x = x.replace('c', '3')
    x = x.replace('C', '3')

    x = x.replace('d', '5')
    x = x.replace('D', '5')

    x = x.replace('ʒ', '6')
    x = x.replace('Ʒ', '6')

    x = x.replace('e', '7')
    x = x.replace('E', '7')
    x = x.replace('é', '7')
    x = x.replace('É', '7')

    x = x.replace('f', '8')
    x = x.replace('F', '8')

    x = x.replace('g0', '9')
    x = x.replace('G0', '9')

    x = x.replace('g', '9')
    x = x.replace('G', '9')

    x = x.replace('ǵ', '9')
    x = x.replace('Ǵ', '9')

    x = x.replace('ǧ0', 'A')
    x = x.replace('Ǧ0', 'A')

    x = x.replace('ǧ', 'A')
    x = x.replace('Ǧ', 'A')

    x = x.replace('i', 'B')
    x = x.replace('I', 'B')
    x = x.replace('í', 'B')
    x = x.replace('Í', 'B')

    x = x.replace('ī', 'B')
    x = x.replace('Ī', 'B')
    x = x.replace('ī́', 'B')
    x = x.replace('Ī́', 'B')

    x = x.replace('j', 'D')
    x = x.replace('J', 'D')

    x = x.replace('kʼ0', 'F')
    x = x.replace('Kʼ0ʼ', 'F')

    x = x.replace('kʼ', 'F')
    x = x.replace('Kʼ', 'F')

    x = x.replace('k0', 'E')
    x = x.replace('K0', 'E')

    x = x.replace('k', 'E')
    x = x.replace('K', 'E')

    x = x.replace('ḱʼ', 'F')
    x = x.replace('Ḱʼ', 'F')

    x = x.replace('ḱ', 'E')
    x = x.replace('Ḱ', 'E')

    x = x.replace('l', 'H')
    x = x.replace('L', 'H')

    x = x.replace('m', 'I')
    x = x.replace('M', 'I')

    x = x.replace('n', 'J')
    x = x.replace('N', 'J')

    x = x.replace('o', 'K')
    x = x.replace('O', 'K')
    x = x.replace('ó', 'K')
    x = x.replace('Ó', 'K')

    x = x.replace('pʼ', 'M')
    x = x.replace('Pʼ', 'M')

    x = x.replace('p', 'L')
    x = x.replace('P', 'L')

    x = x.replace('q0', 'N')
    x = x.replace('Q0', 'N')

    x = x.replace('q', 'N')
    x = x.replace('Q', 'N')

    x = x.replace('r', 'O')
    x = x.replace('R', 'O')

    x = x.replace('s', 'P')
    x = x.replace('S', 'P')

    x = x.replace('tʼ', 'R')
    x = x.replace('Tʼ', 'R')

    x = x.replace('t', 'Q')
    x = x.replace('T', 'Q')

    x = x.replace('u', 'S')
    x = x.replace('U', 'S')
    x = x.replace('ú', 'S')
    x = x.replace('Ú', 'S')

    x = x.replace('ū', 'S')
    x = x.replace('Ū', 'S')
    x = x.replace('ū́', 'S')
    x = x.replace('Ū́', 'S')

    x = x.replace('v', 'T')
    x = x.replace('V', 'T')

    x = x.replace('w', 'U')
    x = x.replace('W', 'U')

    x = x.replace('x0', 'V')
    x = x.replace('X0', 'V')

    x = x.replace('x', 'V')
    x = x.replace('X', 'V')

    x = x.replace('y', 'W')
    x = x.replace('Y', 'W')
    x = x.replace('ý', 'W')
    x = x.replace('Ý', 'W')

    x = x.replace('z', 'X')
    x = x.replace('Z', 'X')

    # return ''.join(abaev_alphabet.get(ch, ch) for ch in x)
    return x


def serialize_dict(dictionary: dict[str, object], file):
    fieldnames = list(asdict(list(dictionary.values())[0]).keys())
    csv_writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=',')
    csv_writer.writeheader()
    for dict_key in dictionary:
        row = {k: v for (k, v) in asdict(dictionary[dict_key]).items()}
        for row_key in row:
            if type(row[row_key]) is list:
                row[row_key] = ",".join(row[row_key])
            if type(row[row_key]) is bool:
                row[row_key] = int(row[row_key])
            if isinstance(row[row_key], Enum):
                row[row_key] = row[row_key].value
        csv_writer.writerow(row)


def get_dict_info(node: etree.ElementBase) -> \
        Tuple[EntryDict, FormDict, SenseGroupDict, SenseDict, ExampleGroupDict, ExampleDict, MentionedDict]:
    entries = EntryDict()
    main_entry = get_entry(node)
    entry_id = main_entry.db_id
    entries[entry_id] = main_entry

    forms = get_forms(node=node,
                      entry_id=entry_id)

    senses, sense_groups = get_senses(node=node,
                                      entry_id=entry_id)

    examples, example_groups = get_examples(node=node, entry_id=entry_id)

    mentioneds = get_mentioneds(node=node,
                                entry_id=entry_id)

    for subentry_node in node.xpath(".//tei:re[not(tei:re) and string(tei:form[@type='lemma']/tei:orth) != '']",
                                    namespaces=NAMESPACES):
        subentry = get_entry(subentry_node)
        subentry.main_entry = entry_id
        if subentry.lemma != '':
            subentry_id = subentry.db_id

            subentry_senses, subentry_sense_groups = get_senses(node=subentry_node,
                                                                entry_id=subentry_id)
            senses = senses | subentry_senses
            sense_groups = sense_groups | subentry_sense_groups

            subentry_examples, subentry_example_groups = get_examples(node=subentry_node,
                                                                      entry_id=subentry_id)
            examples = examples | subentry_examples
            example_groups = example_groups | subentry_example_groups

            entries[subentry.db_id] = subentry

    return entries, forms, sense_groups, senses, example_groups, examples, mentioneds
