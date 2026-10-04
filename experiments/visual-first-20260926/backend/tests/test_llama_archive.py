import hashlib
import unittest
import importlib.util
import pathlib
import sys
_module_path = pathlib.Path(__file__).resolve().parents[1] / "app" / "ai" / "harness" / "llama_archive.py"
_spec = importlib.util.spec_from_file_location("isolated_llama_archive", _module_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
LlamaArchive, VerifiedRecord = _module.LlamaArchive, _module.VerifiedRecord

HASH = hashlib.sha256(b"original").hexdigest()

def fact(tenant="hospital-a", document="frankfurt", verified=True, revision="v1"):
    return VerifiedRecord(tenant, document, revision, 4, "equipment",
                          "System", "OPTIS Mobile Next", "System OPTIS Mobile Next",
                          HASH, verified)

class ArchiveTests(unittest.TestCase):
    def test_real_llamaindex_nodes_and_retrieval(self):
        a = LlamaArchive()
        self.assertEqual(a.rebuild("hospital-a", [fact()]), 1)
        found=a.search("hospital-a", {"frankfurt"}, "OPTIS")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["page"],4)
        self.assertEqual(found[0]["source_sha256"],HASH)

    def test_restrict_tenant_and_document(self):
        a=LlamaArchive()
        a.rebuild("hospital-a",[fact()])
        self.assertEqual(a.search("hospital-b",{"frankfurt"},"OPTIS"),[])
        self.assertEqual(a.search("hospital-a",{"unrelated"},"OPTIS"),[])
        self.assertEqual(a.search("hospital-a",set(),"OPTIS"),[])

    def test_no_unverified_or_cross_tenant_material(self):
        a=LlamaArchive()
        with self.assertRaises(ValueError):
            a.rebuild("hospital-a",[fact(verified=False)])
        with self.assertRaises(ValueError):
            a.rebuild("hospital-b",[fact()])

    def test_rebuild_removes_stale_and_versioned_nodes(self):
        a=LlamaArchive()
        a.rebuild("hospital-a",[fact(),fact(revision="v2")])
        self.assertEqual(len(a.search("hospital-a",{"frankfurt"},"OPTIS")),2)
        a.rebuild("hospital-a",[])
        self.assertEqual(a.search("hospital-a",{"frankfurt"},"OPTIS"),[])

    def test_rebuild_tenant_isolation(self):
        a=LlamaArchive()
        a.rebuild("hospital-a",[fact()])
        a.rebuild("hospital-b",[fact(tenant="hospital-b")])
        a.rebuild("hospital-a",[])
        self.assertEqual(len(a.search("hospital-b",{"frankfurt"},"OPTIS")),1)

if __name__=="__main__":
    unittest.main()
