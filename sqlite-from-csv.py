import sqlalchemy as db
import sqlalchemy_utils as db_utils
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import libabaev2 as abv
import sys

# Database model
Base = declarative_base()


class Language(Base):
    __tablename__ = 'languages'

    lang_id = db.Column(db.Integer, primary_key=True)
    lang_ru = db.Column(db.Text, nullable=False)
    lang_en = db.Column(db.Text, nullable=False)
    glottocode = db.Column(db.Text, nullable=True)
    ISO = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)


class Unit(Base):
    __tablename__ = 'units'

    unit_id = db.Column(db.Integer, primary_key=True)
    xml_id = db.Column(db.Text)
    parent_id = db.Column(db.Integer, default=None)
    full_entry = db.Column(db.Text)
    status = db.Column(db.Integer, default=1, nullable=False)  # will be found in dictionary search (1) or not (?),
    lang_id = db.Column(db.Integer, db.ForeignKey(Language.lang_id), nullable=False)

# Import all Abaev CSV files
langs = abv.LanguageDict.from_csv("../abaev-tei-oxygen/css/langnames.csv")
entries = abv.get_entries_from_csv("csv/entries.csv")
forms = abv.get_forms_from_csv("csv/forms.csv")
senses = abv.get_senses_from_csv("csv/senses.csv")
sense_groups = abv.get_sense_groups_from_csv("csv/senseGroups.csv")
examples = abv.get_examples_from_csv("csv/examples.csv")
example_groups = abv.get_example_groups_from_csv("csv/exampleGroups.csv")
mentioneds = abv.get_mentioneds_from_csv("csv/mentioneds.csv")

# Create SQLite database engine
engine = db.create_engine('sqlite:///abaev.db')
conn = engine.connect()

# Create file if does not exist
if not db_utils.database_exists(engine.url):
    db_utils.create_database(engine.url)

# Create the tables
Base.metadata.create_all(engine)

# Create the session object
Session = sessionmaker(bind=engine)
session = Session()

for lang in langs.values():
    language = Language(
        lang_ru=lang.name_ru,
        lang_en=lang.name_en,
        glottocode=lang.glottocode,
        ISO=lang.code,
        latitude=lang.latitude,
        longitude=lang.longitude
    )
    session.add(language)

for entry in entries.values():
    parent_id = None
    if entry.main_entry:
        parent = session.query(Unit).filter_by(xml_id=entry.main_entry).first()
        parent_id = parent.unit_id
        lang_id = parent.lang_id
        # lang_id = session.query(Language.lang_id).filter_by(ISO=parent.lang_id).first()
    else:
        lang_id = session.query(Language.lang_id).filter_by(ISO=entry.lang).first()[0]
    unit = Unit(
        xml_id=entry.db_id,
        parent_id=parent_id,
        lang_id=lang_id
    )
    session.add(unit)

session.commit()

# for entry in entries.values():
#     conn.execute(
#         units_db.insert().values(unit_id=counter,
#                                  xml_id=entry.db_id,
#                                  parent_id=entry.main_entry, )
#     )