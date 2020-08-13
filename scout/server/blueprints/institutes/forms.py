# -*- coding: utf-8 -*-
import logging
from flask_wtf import FlaskForm
from wtforms.widgets import TextInput
from wtforms import (
    IntegerField,
    SelectMultipleField,
    SubmitField,
    DecimalField,
    TextField,
    validators,
    Field,
    FormField,
    FieldList,
)
from scout.server.extensions import store
from scout.constants import PHENOTYPE_GROUPS

LOG = logging.getLogger(__name__)


def phenotype_choices():
    """Create a list of tuples containing the options for a multiselect"""
    hpo_tuples = []
    for key in PHENOTYPE_GROUPS.keys():
        option_name = " ".join(
            [key, ",", PHENOTYPE_GROUPS[key]["name"], "(", PHENOTYPE_GROUPS[key]["abbr"], ")",]
        )
        hpo_tuples.append((option_name, option_name))

    return hpo_tuples


class NonValidatingSelectMultipleField(SelectMultipleField):
    """Necessary to skip validation of dynamic multiple selects in form"""

    def pre_validate(self, form):
        pass


class HpoListMultiSelect(SelectMultipleField):
    """Validating a multiple select containing a list of HPO terms"""

    def pre_validate(self, form):
        hpo_term = None
        for choice in form.pheno_groups.data:  # chech that HPO terms are valid
            hpo_term = choice.split(" ")[
                0
            ]  # HPO terms formatted like this 'HP:0001298 , Encephalopathy ( ENC )'
            if store.hpo_term(hpo_term) is None:
                form.pheno_groups.errors.append(f"'{hpo_term}' is not a valid HPO term")
                return False


class InstituteForm(FlaskForm):
    """ Instutute-specif settings """

    display_name = TextField(
        "Institute display name",
        validators=[validators.InputRequired(), validators.Length(min=2, max=100)],
    )
    sanger_emails = NonValidatingSelectMultipleField(
        "Sanger recipients", validators=[validators.Optional()]
    )
    coverage_cutoff = IntegerField(
        "Coverage cutoff", validators=[validators.Optional(), validators.NumberRange(min=1)],
    )
    frequency_cutoff = DecimalField(
        "Frequency cutoff",
        validators=[
            validators.Optional(),
            validators.NumberRange(min=0, message="Number must be positive"),
        ],
    )

    pheno_group = TextField("New phenotype group", validators=[validators.Optional()])
    pheno_abbrev = TextField("Abbreviation", validators=[validators.Optional()])

    pheno_groups = NonValidatingSelectMultipleField(
        "Custom phenotype groups", choices=phenotype_choices()
    )
    cohorts = NonValidatingSelectMultipleField(
        "Available patient cohorts", validators=[validators.Optional()]
    )
    institutes = NonValidatingSelectMultipleField("Institutes to share cases with", choices=[])
    submit_btn = SubmitField("Save settings")


# make a base class or other utility with this instead..
class TagListField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return ", ".join(self.data)

        return ""

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(",") if x.strip()]
        else:
            self.data = []


class GeneVariantFiltersForm(FlaskForm):
    """Base FiltersForm for SNVs"""

    variant_type = SelectMultipleField(choices=[("clinical", "clinical"), ("research", "research")])
    hgnc_symbols = TagListField("HGNC Symbols/Ids (case sensitive)")
    filter_variants = SubmitField(label="Filter variants")
    rank_score = IntegerField(default=15)
    phenotype_terms = TagListField("HPO terms")
    phenotype_groups = TagListField("Phenotype groups")
    similar_case = TagListField("Phenotypically similar case")
    cohorts = TagListField("Cohorts")


### Phenopanels form fields ###
class PhenoSubPanelForm(FlaskForm):
    """A form corresponfing to a phenopanel sub-panel"""

    title = TextField("Subpanel title", validators=[validators.InputRequired()])
    subtitle = TextField("Subpanel subtitle", validators=[validators.Optional()])
    pheno_groups = HpoListMultiSelect(
        "Subpanel HPO groups", choices=phenotype_choices(), validators=[validators.InputRequired()]
    )
    add_subpanel = SubmitField("save subpanel")


class PhenoModelForm(FlaskForm):
    """Base Phenopanel form, not including any subpanel"""

    model_name = TextField("Phenotype panel name", validators=[validators.InputRequired()])
    model_desc = TextField("Description", validators=[validators.Optional()])
    # subpanels = FieldList(FormField(PhenoSubPanel()))
    create_model = SubmitField("create")


class MultiCheckboxField(SelectMultipleField):
    """Populates the checkbox list of base terms in a PhenoSubPanel"""

    pass
