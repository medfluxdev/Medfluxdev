import hashlib
import pytest
from app.ai.harness.lexical_archive import Archive, Entry
def entry(t="a", verified=True):
    return Entry(t,"frankfurt","v1",4,"equipment","OPTIS","OPTIS Mobile Next",hashlib.sha256(b"source").hexdigest(),verified)
def test_acl_and_rebuild():
    a=Archive(); a.rebuild("a",[entry()])
    assert len(a.search("a",{"frankfurt"},"OPTIS"))==1
    assert a.search("b",{"frankfurt"},"OPTIS")==[]
    assert a.search("a",{"different"},"OPTIS")==[]
    a.rebuild("a",[])
    assert not a.search("a",{"frankfurt"},"OPTIS")
def test_reject_unverified_cross_tenant():
    a=Archive()
    with pytest.raises(ValueError): a.rebuild("a",[entry(verified=False)])
    with pytest.raises(ValueError): a.rebuild("b",[entry()])