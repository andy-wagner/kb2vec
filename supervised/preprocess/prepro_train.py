import preprocess.prepro_util as prepro_util
import numpy as np
from gensim.models import Doc2Vec
from sqlitedict import SqliteDict
from nltk.tokenize import word_tokenize
from random import shuffle


def load_chunkid2contextid(path='/Users/sevgili/PycharmProjects/group/kb2vec/supervised/preprocess/idmaps/chunkid2contextid.txt'):
    chunk2contextmap = dict()

    with open(path) as fin:
        for line in fin:
            id1, id2 = line.split('\t')
            chunk2contextmap[id1] = int(id2)

    return chunk2contextmap


def load_context_vec(path='/Users/sevgili/PycharmProjects/group/kb2vec/supervised/preprocess/vectors/context_vecs.npy'):
    return np.load(path)


def load_doc2vec(path = '/Users/sevgili/Ozge-PhD/wikipedia-doc2vec/all-dim100/wikipedia_document_dim100_with_wikicorpus.doc2vec'):
    return Doc2Vec.load(path, mmap='r')


def load_longabs(path='/Users/sevgili/Ozge-PhD/DBpedia-datasets/outputs/databases/long_abstracts.db'):
    return SqliteDict(path, autocommit=False)


def load_graphid2url(path='/Users/sevgili/Ozge-PhD/DBpedia-datasets/outputs/databases/intersection_nodes_lookup_inv.db'):
    return SqliteDict(path, autocommit=False)


def load_wikiid2nnid(extension_name=None):
    """returns a map from wiki id to neural network id (for the entity embeddings)"""
    wikiid2nnid = dict()   # wikiid is string,   nnid is integer
    with open("/Users/sevgili/PycharmProjects/end2end_neural_el/data/entities/wikiid2nnid/wikiid2nnid.txt") as fin:
        for line in fin:
            ent_id, nnid = line.split('\t')
            wikiid2nnid[ent_id] = int(nnid) - 1  # torch starts from 1 instead of zero
        assert(wikiid2nnid["1"] == 0)
        assert(-1 not in wikiid2nnid)
        wikiid2nnid["<u>"] = 0
        del wikiid2nnid["1"]
        #print(len(wikiid2nnid))

    if extension_name:
        load_entity_extension(wikiid2nnid, extension_name)
    return wikiid2nnid


def load_entity_extension(wikiid2nnid, extension_name):
    filepath = "/Users/sevgili/PycharmProjects/end2end_neural_el/data/entities/extension_entities/wikiid2nnid/additional_wikiids.txt"
    max_nnid = max(wikiid2nnid.values())
    assert(len(wikiid2nnid) - 1 == max_nnid)
    with open(filepath) as fin:
        line_cnt = 1
        for line in fin:
            ent_id = line.strip()
            if ent_id in wikiid2nnid:   # if extension entities has overlap with the normal entities set
                wikiid2nnid[ent_id + "dupl"] = max_nnid + line_cnt    # this vector is duplicate and is never going to be used
            else:
                wikiid2nnid[ent_id] = max_nnid + line_cnt
            line_cnt += 1
    print("original entities: ", max_nnid + 1, " extension entities: ", len(wikiid2nnid) - (max_nnid+1))


def load_graph_vec(path='/Users/sevgili/PycharmProjects/end2end_neural_el/data/entities/ent_vecs/ent_vecs_graph.npy'):
    return np.load(path)


def load_graph2wiki(path='/Users/sevgili/PycharmProjects/end2end_neural_el/data/entities/wikiid2nnid/graphid2wikiid.txt'):
    id2idmap = dict()
    multiple_references = set()
    with open(path) as fin:
        for line in fin:
            id1, id2 = line.split('\t')
            id1, id2 = int(id1), int(id2)
            try:
                id2idmap[id1].add(id2)
                multiple_references.add(id1)
            except:
                id2idmap[id1] = set()
                id2idmap[id1].add(id2)

    #print(count, len(multiple_references))
    return id2idmap, multiple_references


class InputVecGenerator(object):
    def __init__(self):
        self.sample_generator = prepro_util.InputSamplesGenerator()
        self.chunkid2contextid = load_chunkid2contextid()
        self.context_vecs = load_context_vec()
        self.doc2vec = load_doc2vec()
        self.wiki2nn = load_wikiid2nnid(extension_name='extension_entities')
        self.url2longabs = load_longabs()
        self.graph_vecs = load_graph_vec()
        self.graphid2wikiid,_ = load_graph2wiki()
        self.graphid2url = load_graphid2url()

    def create_input_vec(self, sample):

        chunk_id, chunk_words, begin_gm, end_gm, ground_truth, cand_entities, cand_entities_scores = sample
        count_except = 0
        for index in range(len(begin_gm)):
            candidate_entities_, ground_truth_id, begin, end = cand_entities[index],\
                                                               ground_truth[index], begin_gm[index], end_gm[index]
            #print(ground_truth_id, begin, end)

            if ground_truth != -1 or len(candidate_entities_) > 0: # for the one we have the correct result
                context_vec = self.context_vecs[self.chunkid2contextid[chunk_id]]
                span_text = ' '.join(chunk_words[begin:end])
                try:
                    word_vec = self.doc2vec[span_text]
                except KeyError:
                    word_vec = self.doc2vec.infer_vector(span_text)

                for cand in candidate_entities_:

                    try:
                        longab = self.url2longabs[self.graphid2url[cand]]
                        longab_vec = self.doc2vec.infer_vector(word_tokenize(longab))
                    except:
                        count_except += 1
                        continue
                        #return -1
                    try:
                        wiki_id = self.graphid2wikiid[int(cand)].pop()
                    except:
                        count_except += 1
                        continue

                    nn_id = self.wiki2nn[str(wiki_id)]
                    graph_vec = self.graph_vecs[int(nn_id)]

                    inputvec = np.concatenate((np.array(word_vec), np.array(graph_vec),
                                        np.array(context_vec), np.array(longab_vec)), axis=0)

                    if int(cand) == int(ground_truth_id):
                        # 1 means positive
                        yield (inputvec, np.array([1]))
                    else:
                        # 0 means negative
                        yield (inputvec, np.array([0]))
        #print(count_except)

    def format(self, list_sample):
        inputs, outputs = list(), list()
        index = 0

        for sample in list_sample:
            inputs.insert(index, sample[0])
            outputs.insert(index, sample[1])
            index += 1

        return np.array(inputs), np.array(outputs)

    # path of dataset
    def process(self, path='/Users/sevgili/PycharmProjects/end2end_neural_el/data/new_datasets/ace2004.txt', ttl=False):
        samples = list()
        for sample in self.sample_generator.process(path, ttl=ttl):

            #chunk_id, chunk_words, begin_gm, end_gm, ground_truth, cand_entities, cand_entities_scores = sample
            #print(chunk_words, begin_gm, end_gm, cand_entities)
            #print('lengths', len(begin_gm), len(end_gm), len(cand_entities))
            for input_vec in self.create_input_vec(sample):
                samples.append(input_vec)

        print('finished creating input files', len(samples))
        shuffle(samples)
        print('finished shuffling samples')
        inputs, outputs = self.format(samples)
        print('finished formatting')
        return inputs, outputs


if __name__ == "__main__":
    inputvecgenerator = InputVecGenerator()
    inputvecgenerator.process()
