# -*- coding: utf-8 -*-
import logging
import datetime

import operator
from treelib import Node, Tree
from pymongo.errors import DuplicateKeyError, BulkWriteError
import pymongo

from scout.exceptions import IntegrityError
from scout.utils.md5 import generate_md5_key

LOG = logging.getLogger(__name__)


class HpoHandler(object):
    def load_hpo_term(self, hpo_obj):
        """Add a hpo object

        Arguments:
            hpo_obj(dict)

        """
        LOG.debug("Loading hpo term %s into database", hpo_obj["_id"])
        try:
            self.hpo_term_collection.insert_one(hpo_obj)
        except DuplicateKeyError as err:
            raise IntegrityError("Hpo term %s already exists in database".format(hpo_obj["_id"]))
        LOG.debug("Hpo term saved")

    def load_hpo_bulk(self, hpo_bulk):
        """Add a hpo object

        Arguments:
            hpo_bulk(list(scout.models.HpoTerm))

        Returns:
            result: pymongo bulkwrite result

        """
        LOG.debug("Loading hpo bulk")

        try:
            result = self.hpo_term_collection.insert_many(hpo_bulk)
        except (DuplicateKeyError, BulkWriteError) as err:
            raise IntegrityError(err)
        return result

    def hpo_term(self, hpo_id):
        """Fetch a hpo term

        Args:
            hpo_id(str)

        Returns:
            hpo_obj(dict)
        """
        LOG.debug("Fetching hpo term %s", hpo_id)

        return self.hpo_term_collection.find_one({"_id": hpo_id})

    def hpo_terms(self, query=None, hpo_term=None, text=None, limit=None):
        """Return all HPO terms

        If a query is sent hpo_terms will try to match with regex on term or
        description.

        Args:
            query(str): Part of a hpoterm or description
            hpo_term(str): Search for a specific hpo term
            limit(int): the number of desired results

        Returns:
            result(pymongo.Cursor): A cursor with hpo terms
        """
        query_dict = {}
        search_term = None
        if query:
            query_dict = {
                "$or": [
                    {"hpo_id": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]
            }
            search_term = query
        elif text:
            new_string = ""
            for i, word in enumerate(text.split(" ")):
                if i == 0:
                    new_string += word
                else:
                    new_string += ' "{0}"'.format(word)
            LOG.info("Search HPO terms with %s", new_string)
            query_dict["$text"] = {"$search": new_string}
            search_term = text
        elif hpo_term:
            query_dict["hpo_id"] = hpo_term
            search_term = hpo_term

        limit = limit or int(10e10)
        res = (
            self.hpo_term_collection.find(query_dict)
            .limit(limit)
            .sort("hpo_number", pymongo.ASCENDING)
        )

        return res

    def generate_hpo_gene_list(self, *hpo_terms):
        """Generate a sorted list with namedtuples of hpogenes
            Each namedtuple of the list looks like (hgnc_id, count)
            Args:
                hpo_terms(iterable(str))
            Returns:
                hpo_genes(list(HpoGene))
        """
        genes = {}
        for term in hpo_terms:
            hpo_obj = self.hpo_term(term)
            if hpo_obj:
                for hgnc_id in hpo_obj["genes"]:
                    if hgnc_id in genes:
                        genes[hgnc_id] += 1
                    else:
                        genes[hgnc_id] = 1
            else:
                LOG.warning("Term %s could not be found", term)

        sorted_genes = sorted(genes.items(), key=operator.itemgetter(1), reverse=True)
        return sorted_genes

    def phenomodels(self, institute_id=None, model_id=None):
        """Return all phenopanels for a given institute

        Args:
            institute_id(str): institute id
            model_id(str): phenomodel id

        Returns:
            phenotype_models(pymongo.cursor.Cursor)
        """
        if model_id is not None:
            query = {"_id": model_id}
        else:
            query = {"institute": institute_id}
        phenotype_models = self.phenomodel_collection.find(query)
        return phenotype_models

    def create_phenomodel(self, id, institute_id, name, description):
        """Create an empty advanced phenotype model with data provided by a user

        Args:
            id(str) a md5_key id
            institute_id(str): institute id
            name(str) a panel name
            description(str) a panel description

        Returns:
            phenopanel_obj(dict) a newly created panel
        """
        phenomodel_obj = dict(
            _id=id,
            institute=institute_id,
            name=name,
            description=description,
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )
        phenomodel_obj = self.phenomodel_collection.insert_one(phenomodel_obj)
        return phenomodel_obj

    def build_phenotype_tree(self, hpo_ids):
        """Creates an HPO Tree based on one or more given ancestors
        Args:
            hpo_id(str): an HPO term (ancestor)
        Returns:
            hpo_tree(treelib.Tree): a tree of all children HPO terms
        """
        tree = Tree()
        tree.create_node("root", "root")
        all_terms = {}

        def _hpo_terms_list(hpo_ids):
            for id in hpo_ids:
                term_obj = self.hpo_term(id)
                if term_obj is None:
                    continue
                if tree.get_node(id) is None:  # no duplicated nodes
                    tree.create_node(
                        id,
                        id,
                        parent="root",
                        data={"hpo_id": id, "description": term_obj["description"]},
                    )
                all_terms[id] = term_obj
                _hpo_terms_list(term_obj["children"])

        # compile a list of all HPO term objects to include in the submodel
        _hpo_terms_list(hpo_ids)

        # Organize the tree according to the ontology
        for key, term in all_terms.items():
            ancestors = term["ancestors"]
            if len(ancestors) == 0:
                continue
            for ancestor in ancestors:
                if ancestor == "root" or tree.get_node(ancestor) is None:
                    continue
                # if ancestor node exists move this node under the ancestor
                try:
                    tree.move_node(key, ancestor)
                except Exception as ex:
                    LOG.warning(f"Error trying to move {key} from root to {ancestor}!")

        LOG.info(f"Built ontology for HPO terms:{hpo_ids}:\n{tree}")
        return tree

    def add_pheno_submodel(self, model_id, submodel_title, submodel_subtitle, hpo_ids):
        """Adds a new phenotype submodel (one or more HPO terms with their children) to a phenotype model.

        Args:
            model_id(str): id of a phenotype model
            submodel_title(str): title of submodel
            submodel_subtitle(str): subtitle of submodel
            hpo_ids(list): a list of HPO term IDs (example HP:0012759)

        Returns:
            updated_model(dict): a dictionary corresponding to the updated phenotype model
        """
        # Create an HPO tree for each of the ancestror terms
        hpo_tree = self.build_phenotype_tree(hpo_ids)
        if hpo_tree is None:
            return
        tree_obj = hpo_tree.to_dict(with_data=True)

        # update model by adding the new submodel
        submodel_id = generate_md5_key([model_id, submodel_title])
        submodel_obj = dict(
            title=submodel_title,
            subtitle=submodel_subtitle,
            hpo_groups=tree_obj,
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )

        updated_model = self.phenomodel_collection.find_one_and_update(
            {"_id": model_id},
            {
                "$set": {
                    ".".join(["submodels", submodel_id]): submodel_obj,
                    "updated": datetime.datetime.now(),
                }
            },
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return updated_model
