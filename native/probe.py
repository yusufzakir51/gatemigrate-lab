#!/usr/bin/env python3
"""Raw GateMigrate native observations v2; never a calibration verdict.

Requires Python 3.9+ and, only for write probing, Git. No third-party packages.
All Git calls use argument arrays. Credentials and captured Git output are never
printed or written. V2 adds bounded diagnostic identifiers, not raw error text,
after attempted pushes. The write probe only creates a new run-specific branch
in an explicitly acknowledged disposable repository and never deletes a branch.
"""
import argparse
import datetime as dt
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

PUBLIC_CANARY = "GateMigrate-public-calibration-canary-v1"
SCHEMA_VERSION = "gatemigrate.raw-native-observation.v1"
PROBE_VERSION = "gatemigrate.native-probe.v2"


def push_diagnostics(platform, repository, returncode, stderr):
    """Recognize only exact, English provider message patterns; return constants.

    These are observations of provider text, not a permission/effect verdict.
    Unknown errors (including a bare HTTP 403), other permissions, local errors,
    and changed/localized messages deliberately remain unclassified. A matched
    message still requires independent token/settings and branch readback.

    Sources checked 2026-10-10:
    - GitHub Docs: /en/authentication/troubleshooting-ssh/
      error-permission-to-userrepo-denied-to-other-user (message pattern).
    - https://github.com/orgs/community/discussions/46398 (primary error report
      for the alternate exact GitHub message, NOT an API format guarantee).
    - https://github.com/githubnext/ado-aw/blob/main/docs/safe-output-permissions.md
      (tool-author documentation of TF401027/GenericContribute).
    - https://learn.microsoft.com/en-us/answers/questions/316908/
      creating-data-factory-pipeline-from-vso-deployment (primary CreateBranch
      error report, NOT an API format guarantee).
    - Microsoft Learn /en-us/azure/devops/pipelines/scripts/git-commands explains
      Build Service Create branch/Contribute grants; it does not promise strings.
    """
    signals = set()
    if returncode != 0 and isinstance(stderr, str):
        for line in stderr.splitlines():
            if platform == "github":
                if line == "remote: Write access to repository not granted.":
                    signals.add("GITHUB_WRITE_ACCESS_NOT_GRANTED_TEXT")
                if (re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
                        and re.fullmatch(
                            r"remote: Permission to " + re.escape(repository)
                            + r"(?:\.git)? denied to [A-Za-z0-9_.\[\]-]+\.", line)):
                    signals.add("GITHUB_REPOSITORY_PERMISSION_DENIED_TEXT")
            elif platform == "azure":
                # Some Git receive-pack responses prepend a hexadecimal packet
                # length to the otherwise identical TF401027 sentence.
                match = re.fullmatch(
                    r"remote: (?:[0-9a-f]{1,16})?TF401027: You need the Git "
                    r"'(GenericContribute|CreateBranch)' permission to perform this action\."
                    r"(?: ?Details: .*)?", line)
                if match:
                    signals.add({
                        "GenericContribute": "AZURE_TF401027_GENERIC_CONTRIBUTE_TEXT",
                        "CreateBranch": "AZURE_TF401027_CREATE_BRANCH_TEXT",
                    }[match.group(1)])
    return {
        "parser_version": "gatemigrate.git-diagnostics.v1",
        "provider_message_signals": sorted(signals),
        "raw_output_logged": False,
        "interpretation": "OBSERVATION_ONLY_REQUIRES_INDEPENDENT_CORROBORATION",
    }


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def getenv(name, fallback="unknown"):
    return os.environ.get(name, "").strip() or fallback


def context():
    platform = getenv("GM_PLATFORM")
    if platform == "github":
        return dict(platform=platform, run_id=getenv("GITHUB_RUN_ID"),
                    attempt=getenv("GITHUB_RUN_ATTEMPT"),
                    candidate_hash=getenv("GITHUB_SHA"),
                    actor=getenv("GITHUB_ACTOR"), resource=getenv("GITHUB_REPOSITORY"),
                    ref=getenv("GITHUB_REF"), event=getenv("GITHUB_EVENT_NAME"))
    if platform == "azure":
        return dict(platform=platform, run_id=getenv("BUILD_BUILDID"),
                    attempt=getenv("SYSTEM_JOBATTEMPT"),
                    candidate_hash=getenv("BUILD_SOURCEVERSION"),
                    actor=getenv("BUILD_REQUESTEDFORID"), resource=getenv("BUILD_REPOSITORY_URI"),
                    ref=getenv("BUILD_SOURCEBRANCH"), event=getenv("BUILD_REASON"))
    return dict(platform="local", run_id="local", attempt="0", candidate_hash="unknown",
                actor="local", resource="local", ref="unknown", event="local")


def observation(args, name, detail):
    record = dict(schema_version=SCHEMA_VERSION, probe_version=PROBE_VERSION, probe_type=args.probe,
                  family=args.family, **context(), observed_utc=now(),
                  scenario_id=getenv("GM_SCENARIO_ID"),
                  settings_snapshot_digest=getenv("GM_SETTINGS_SNAPSHOT_DIGEST"),
                  observation=name, detail=detail,
                  local_record_only=context()["platform"] == "local",
                  calibration_verdict="NOT_EVALUATED")
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    # This is the only stdout emission path. No environment value used as a
    # canary, credential, Git stdout, or Git stderr is included in this record.
    print(line)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    return record


def canonical_repo(url):
    """Accept only supported HTTPS remotes, with no query or fragment."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.query or parsed.fragment or parsed.password:
            return None
        if parsed.hostname not in {"github.com", "dev.azure.com"} or parsed.port not in (None, 443):
            return None
        path = unquote(parsed.path).rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if parsed.hostname == "github.com":
            if not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path):
                return None
        else:
            # Azure organization/project/repository names may contain spaces.
            if not re.fullmatch(r"/[^/]+/[^/]+/_git/[^/]+", path):
                return None
        return "https://" + parsed.hostname + path
    except ValueError:
        return None


def git(*arguments):
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    return subprocess.run(["git", *arguments], capture_output=True, text=True,
                          timeout=45, env=env, check=False)


def probe_write(args):
    ctx = context()
    guards = {
        "explicit_opt_in": getenv("GATEMIGRATE_ENABLE_WRITE_PROBE", "false").lower() == "true",
        "disposable_confirmation": getenv("GM_DISPOSABLE_LAB_CONFIRM", "") == "disposable-lab-only",
        "native_platform": ctx["platform"] in {"github", "azure"},
        "supported_ref": ctx["ref"] in {"refs/heads/main", "refs/heads/gm-untrusted"},
        "supported_manual_event": ((ctx["platform"] == "github" and ctx["event"] == "workflow_dispatch")
                                   or (ctx["platform"] == "azure" and ctx["event"] == "Manual")),
    }
    declared = canonical_repo(getenv("GM_LAB_REPOSITORY_URL", ""))
    actual = canonical_repo("https://github.com/" + ctx["resource"] if ctx["platform"] == "github"
                            else ctx["resource"])
    guards["configured_repository_matches_run"] = bool(declared and actual and declared == actual)
    if not all(guards.values()):
        return observation(args, "WRITE_NOT_ATTEMPTED", {"guards": guards,
                           "meaning": "A disabled or unconfigured probe is not a policy denial."})
    run = ctx["run_id"] + "-" + ctx["attempt"]
    if not re.fullmatch(r"[0-9]+-[0-9]+", run):
        return observation(args, "WRITE_NOT_ATTEMPTED", {"reason": "invalid_run_identifier"})
    ref = "refs/heads/gm-probe/" + ctx["platform"] + "-" + run
    try:
        fetch_urls = git("remote", "get-url", "--all", "origin")
        push_urls = git("remote", "get-url", "--push", "--all", "origin")
        urls = fetch_urls.stdout.splitlines() + push_urls.stdout.splitlines()
        if (fetch_urls.returncode or push_urls.returncode or len(urls) != 2
                or any(canonical_repo(u) != declared for u in urls)):
            return observation(args, "WRITE_NOT_ATTEMPTED", {"reason": "remote_identity_unverified"})
        head = git("rev-parse", "HEAD")
        sha = head.stdout.strip()
        if head.returncode or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            return observation(args, "WRITE_NOT_ATTEMPTED", {"reason": "head_unavailable"})
        if sha.lower() != ctx["candidate_hash"].lower():
            return observation(args, "WRITE_NOT_ATTEMPTED", {"reason": "candidate_head_mismatch"})
        pre = git("ls-remote", "--exit-code", "--heads", "origin", ref)
        # Git ls-remote returns 2 when no matching ref exists. Other errors are
        # ambiguous and must never be converted into an authorization denial.
        if pre.returncode != 2:
            return observation(args, "WRITE_NOT_ATTEMPTED", {"reason": "new_branch_precondition_unmet",
                              "git_returncode": pre.returncode, "branch_ref": ref})
        # An empty expected object after ':' means the branch must not exist.
        # This lease prevents a race from overwriting any existing branch.
        pushed = git("-c", "core.hooksPath=/dev/null", "push", "--porcelain",
                     "--force-with-lease=" + ref + ":", "origin", sha + ":" + ref)
        name = "PUSH_REPORTED_SUCCESS" if pushed.returncode == 0 else "PUSH_INCONCLUSIVE_ERROR"
        return observation(args, name, {"git_returncode": pushed.returncode, "branch_ref": ref,
                           "expected_object_id": sha, "external_effect_verification": "PENDING",
                           "push_diagnostics": push_diagnostics(ctx["platform"], ctx["resource"],
                                                                pushed.returncode, pushed.stderr),
                           "meaning": "Independent repository readback and policy evidence are required."})
    except (OSError, subprocess.TimeoutExpired):
        return observation(args, "PUSH_INCONCLUSIVE_ERROR", {
                           "reason": "git_unavailable_or_timeout", "branch_ref": ref,
                           "external_effect_verification": "PENDING",
                           "meaning": "A timeout may occur after a remote effect; inspect the branch."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", choices=("marker", "canary", "write"))
    parser.add_argument("--family", choices=("deployment_authorization", "approval_enforcement",
                                             "synthetic_secret_access", "repository_write"), required=True)
    parser.add_argument("--label", default="unspecified")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if args.probe == "marker":
        observation(args, "MARKER_REACHED", {"label": args.label,
                    "meaning": "This process started; join to independent stage/job and gate timelines."})
    elif args.probe == "canary":
        value = os.environ.get("GM_CANARY_VALUE", "")
        if re.fullmatch(r"\$\([A-Za-z0-9_]+\)", value):
            status = "CANARY_MAPPING_UNRESOLVED"
        elif not value:
            status = "CANARY_EMPTY"
        elif hmac.compare_digest(value.encode(), PUBLIC_CANARY.encode()):
            status = "PUBLIC_CANARY_MATCH"
        else:
            status = "CANARY_MISMATCH"
        observation(args, status, {"label": args.label, "value_logged": False,
                    "meaning": "Availability of a known public calibration value only; not confidentiality proof."})
    else:
        probe_write(args)


if __name__ == "__main__":
    main()
