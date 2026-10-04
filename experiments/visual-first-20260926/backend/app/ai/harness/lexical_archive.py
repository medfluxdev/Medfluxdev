"""Isolated rebuildable lexical archive; not canonical storage or LlamaIndex."""
from dataclasses import dataclass
import sqlite3

@dataclass(frozen=True)
class Entry:
    tenant: str
    document: str
    version: str
    page: int
    field: str
    value: str
    quote: str
    source_hash: str
    verified: bool

class Archive:
    def __init__(self):
        self.db=sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE entries (tenant TEXT,document TEXT,version TEXT,page INT,field TEXT,value TEXT,quote TEXT,hash TEXT)")
    def rebuild(self, tenant: str, entries: list[Entry]):
        if not tenant or any(x.tenant!=tenant or not x.verified or not x.quote
                             or x.page<1 or len(x.source_hash)!=64 for x in entries):
            raise ValueError("unverified or unscoped evidence")
        with self.db:
            self.db.execute("DELETE FROM entries WHERE tenant=?", (tenant,))
            self.db.executemany("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)",
                [(x.tenant,x.document,x.version,x.page,x.field,x.value,x.quote,x.source_hash) for x in entries])
    def search(self, tenant: str, allowed_documents: set[str], query: str):
        if not tenant or not allowed_documents or not query.strip():
            return []
        q="SELECT document,version,page,field,value,quote,hash FROM entries WHERE tenant=? AND document IN ("+ ",".join("?" for _ in allowed_documents)+")"
        records=self.db.execute(q,(tenant,*sorted(allowed_documents))).fetchall()
        return [r for r in records if all(t in " ".join(map(str,r)).casefold() for t in query.casefold().split())]