#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE="https://github.com/decompme/compilers/releases/download/compilers"
API="https://api.github.com/repos/decompme/compilers/releases/tags/compilers"

list_assets() {
    curl -sfL "$API" | python3 -c "
import json,sys
for a in sorted(json.load(sys.stdin).get('assets',[]), key=lambda a:a['name']):
    if a['name'].startswith('ee-'):
        print(a['name'])
"
}

if [ "${1:-}" = "--list" ]; then
    list_assets
    exit 0
fi

COMPILER_ID="${1:-ee-gcc2.9-991111-01}"
COMPILER_DIR="$ROOT/tools/compilers/$COMPILER_ID"

if [ ! -d "$COMPILER_DIR" ]; then
    ASSET="$(list_assets | grep -E "^${COMPILER_ID}\.tar\.(gz|xz)$" | head -1 || true)"
    if [ -z "$ASSET" ]; then
        echo "!! no published asset for '$COMPILER_ID'. available:" >&2
        list_assets | sed 's/\.tar\.[gx]z$//' | sed 's/^/     /' >&2
        exit 1
    fi
    echo ">> fetching $ASSET"
    mkdir -p "$COMPILER_DIR"
    case "$ASSET" in
        *.tar.xz) TARFLAG=J ;;
        *.tar.gz) TARFLAG=z ;;
    esac
    curl -fL "$RELEASE/$ASSET" | tar -x${TARFLAG} -C "$COMPILER_DIR"
fi

echo ">> contents of $COMPILER_ID:"
find "$COMPILER_DIR" -type f | sed "s|$COMPILER_DIR/|     |"

WIBO="$ROOT/tools/wibo"
if find "$COMPILER_DIR" -name '*.exe' -type f | grep -q .; then
    if [ ! -x "$WIBO" ]; then
        echo ">> PE binaries detected, fetching wibo"
        curl -fL -o "$WIBO" \
            "https://github.com/decompals/wibo/releases/latest/download/wibo" \
            && chmod +x "$WIBO" \
            || echo "!! fetch wibo manually from github.com/decompals/wibo/releases" >&2
    fi
    [ -x "$WIBO" ] && echo ">> wibo:    $WIBO"
fi

find_one() {
    find "$COMPILER_DIR" \( -name "$1" -o -name "$1.exe" \) -type f | head -1
}

CC1PLUS="$(find_one cc1plus)"
DRIVER="$(find_one ee-g++)"
[ -z "$DRIVER" ] && DRIVER="$(find_one ee-gcc)"

if [ -n "$CC1PLUS" ]; then
    echo ">> cc1plus: $CC1PLUS"
elif [ -n "$DRIVER" ]; then
    echo ">> driver:  $DRIVER"
    echo "   !! no cc1plus in this tarball -- C++ will not build."
    echo "      Try another id; 'bash tools/setup.sh --list' shows all."
else
    echo "!! no compiler backend found under $COMPILER_DIR" >&2
    exit 1
fi

OBJDIFF="$ROOT/tools/objdiff-cli"
if [ ! -x "$OBJDIFF" ]; then
    echo ">> fetching objdiff-cli"
    case "$(uname -s)" in
        Linux)  ASSET="objdiff-cli-linux-$(uname -m)" ;;
        Darwin) ASSET="objdiff-cli-macos-$(uname -m)" ;;
        *)      ASSET="" ;;
    esac
    if [ -n "$ASSET" ]; then
        curl -fL -o "$OBJDIFF" \
            "https://github.com/encounter/objdiff/releases/latest/download/${ASSET}" \
            && chmod +x "$OBJDIFF" \
            || echo "!! asset name may have changed; check the releases page" >&2
    fi
fi

echo ">> python tooling"
python3 -m pip install -U "splat64[mips]" ninja

for repo in m2c decomp-permuter; do
    if [ ! -d "$ROOT/tools/$repo" ]; then
        case "$repo" in
            m2c)             url="https://github.com/matt-kempster/m2c" ;;
            decomp-permuter) url="https://github.com/simonlindholm/decomp-permuter" ;;
        esac
        git clone --depth 1 "$url" "$ROOT/tools/$repo"
        [ -f "$ROOT/tools/$repo/requirements.txt" ] && \
            python3 -m pip install -r "$ROOT/tools/$repo/requirements.txt"
    fi
done

echo
echo "Set COMPILER_ID = \"$COMPILER_ID\" in configure.py"
