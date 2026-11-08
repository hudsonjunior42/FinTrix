#!/usr/bin/env python3
"""Servidor S3 mínimo para testar a sincronização sem um bucket de verdade (só o que o cofre usa:
listar com prefixo, ler e gravar objetos). Não confere assinaturas: serve só para testes, em 127.0.0.1.

O app aceita http só no build de debug. Para o celular pela USB: adb reverse tcp:9000 tcp:9000.

Uso: python3 test/s3_local.py [pasta] [porta]     (padrão: pasta temporária, porta 9000)
No app: endpoint http://127.0.0.1:9000, qualquer bucket, região e chaves.
"""
import email.utils
import hashlib
import http.server
import pathlib
import sys
import tempfile
import urllib.parse
from xml.sax.saxutils import escape

RAIZ = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="s3-local-"))
PORTA = int(sys.argv[2]) if len(sys.argv) > 2 else 9000


def caminho(bucket: str, chave: str) -> pathlib.Path:
    p = (RAIZ / bucket / chave).resolve()
    if not str(p).startswith(str(RAIZ.resolve()) + "/"):
        raise ValueError("fora da pasta")
    return p


def etag(dados: bytes) -> str:
    return '"' + hashlib.md5(dados).hexdigest() + '"'


class S3(http.server.BaseHTTPRequestHandler):
    def partes(self):
        u = urllib.parse.urlsplit(self.path)
        bucket, _, chave = urllib.parse.unquote(u.path).lstrip("/").partition("/")
        return bucket, chave, urllib.parse.parse_qs(u.query)

    def responder(self, cod, corpo=b"", tipo="application/xml", extra=None):
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def do_PUT(self):
        bucket, chave, _ = self.partes()
        dados = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not chave:  # criar bucket
            (RAIZ / bucket).mkdir(parents=True, exist_ok=True)
            return self.responder(200)
        p = caminho(bucket, chave)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados)
        self.responder(200, extra={"ETag": etag(dados)})

    def do_GET(self):
        bucket, chave, q = self.partes()
        if not chave:
            return self.listar(bucket, q.get("prefix", [""])[0])
        p = caminho(bucket, chave)
        if not p.is_file():
            return self.responder(404, b"<Error><Code>NoSuchKey</Code></Error>")
        dados = p.read_bytes()
        self.responder(200, dados, "application/octet-stream",
                       {"ETag": etag(dados), "Last-Modified": email.utils.formatdate(p.stat().st_mtime, usegmt=True)})

    do_HEAD = do_GET

    def listar(self, bucket, prefixo):
        base = RAIZ / bucket
        itens = []
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                chave = p.relative_to(base).as_posix()
                if p.is_file() and chave.startswith(prefixo):
                    st = p.stat()
                    quando = email.utils.formatdate(st.st_mtime, usegmt=True)
                    iso = email.utils.parsedate_to_datetime(quando).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    itens.append(f"<Contents><Key>{escape(chave)}</Key><LastModified>{iso}</LastModified>"
                                 f"<ETag>{escape(etag(p.read_bytes()))}</ETag><Size>{st.st_size}</Size>"
                                 f"<StorageClass>STANDARD</StorageClass></Contents>")
        xml = ('<?xml version="1.0" encoding="UTF-8"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
               f"<Name>{escape(bucket)}</Name><Prefix>{escape(prefixo)}</Prefix><KeyCount>{len(itens)}</KeyCount>"
               f"<MaxKeys>1000</MaxKeys><IsTruncated>false</IsTruncated>{''.join(itens)}</ListBucketResult>")
        self.responder(200, xml.encode())

    def log_message(self, fmt, *args):
        sys.stderr.write("s3_local: " + (fmt % args) + "\n")


if __name__ == "__main__":
    print(f"S3 local em http://127.0.0.1:{PORTA} (pasta {RAIZ})", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", PORTA), S3).serve_forever()
