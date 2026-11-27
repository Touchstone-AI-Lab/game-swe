"""Stage pinned upstream sources and portable build archives without editing clones."""

import argparse
import json
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--lock", type=Path, required=True)
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--existing-repos", type=Path)
args = parser.parse_args()
workspace = args.workspace.resolve()
workspace.mkdir(parents=True, exist_ok=True)
lock = json.loads(args.lock.read_text())
namespace = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", namespace)


def q(name: str) -> str:
    return "{" + namespace + "}" + name


(workspace / "archives").mkdir(exist_ok=True)
for name, origin in lock.items():
    source = args.existing_repos / name if args.existing_repos else workspace / "repos" / name
    if not source.exists():
        assert args.existing_repos is None, source
        subprocess.run(["git", "init", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "remote", "add", "origin", origin["url"]], check=True)
        subprocess.run(
            ["git", "-C", str(source), "fetch", "--depth=1", "origin", origin["commit"]], check=True
        )
        subprocess.run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], check=True)
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    assert actual == origin["commit"], (name, actual)
    assert not subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain"], text=True
    ).strip(), source
    target = workspace / "sources" / name
    assert not target.exists(), f"Refusing to overwrite source staging: {target}"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", "target", "*.psd", "*.xcf"))
    if name == "PackmasterCharacter":
        shutil.copyfile(target / "example-pom.txt", target / "pom.xml")
    for pom in target.rglob("pom.xml"):
        tree = ET.parse(pom)
        root = tree.getroot()
        for node in root.iter(q("systemPath")):
            assert node.text is not None, "Expected a systemPath value"
            node.text = "/opt/sts/lib/" + node.text.replace("\\", "/").split("/")[-1]
        for plugins in root.iter(q("plugins")):
            for plugin in list(plugins):
                if plugin.findtext(q("artifactId")) == "maven-antrun-plugin":
                    plugins.remove(plugin)
        properties = root.find(q("properties"))
        if properties is None:
            properties = ET.SubElement(root, q("properties"))
        encoding = properties.find(q("project.build.sourceEncoding"))
        if encoding is None:
            encoding = ET.SubElement(properties, q("project.build.sourceEncoding"))
        encoding.text = "UTF-8"
        tree.write(pom, encoding="utf-8", xml_declaration=True)
    for java in target.rglob("*.java"):
        content = java.read_bytes().replace(b"\r\n", b"\n")
        if java.name == "UpdateWindow.java":
            content = content.replace(b"import javafx.util.Pair;", b"")
        java.write_bytes(content)
    with tarfile.open(
        workspace / "archives" / (name + ".tar.gz"), "w:gz", format=tarfile.GNU_FORMAT
    ) as archive:
        archive.add(target, arcname=name)
    print("STAGED", name, actual, flush=True)
(workspace / "source-lock.json").write_text(json.dumps(lock, indent=2))
