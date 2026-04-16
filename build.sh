#!/bin/sh

COMPONENTS="prepare vp report database media sipp opensips"

usage() {
    echo "Usage: $0 [-c|--clean] [-r|--refresh [component,...]]"
    echo ""
    echo "Options:"
    echo "  -c, --clean                   Stop/remove all VOLTS containers and images"
    echo "  -r, --refresh                 Force rebuild all components (--no-cache)"
    echo "  -r, --refresh comp1[,comp2,...]  Force rebuild specific component(s) (--no-cache)"
    echo ""
    echo "Components: $COMPONENTS"
    exit 1
}

REBUILD_COMPONENTS=""
CLEAN=0

while [ $# -gt 0 ]; do
    case "$1" in
        -c|--clean)
            CLEAN=1
            shift
            ;;
        -r|--refresh)
            shift
            if [ -n "$1" ] && [ "${1#-}" = "$1" ]; then
                REBUILD_COMPONENTS=$(echo "$1" | tr ',' ' ')
                shift
            else
                REBUILD_COMPONENTS="$COMPONENTS"
            fi
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [ "$CLEAN" = "1" ]; then
    echo "Cleaning VOLTS containers and images..."
    for comp in $COMPONENTS; do
        docker ps -q --filter "ancestor=volts_$comp" | xargs -r docker stop
        docker ps -aq --filter "ancestor=volts_$comp" | xargs -r docker rm
        docker image rm "volts_$comp:latest" >> /dev/null 2>&1
    done
    exit 0
fi

should_rebuild() {
    comp="$1"
    [ -z "$REBUILD_COMPONENTS" ] && return 1
    for c in $REBUILD_COMPONENTS; do
        [ "$c" = "$comp" ] && return 0
    done
    return 1
}

for comp in $COMPONENTS; do
    tag="volts_$comp"
    cache_opt=""

    if should_rebuild "$comp"; then
        docker image rm "$tag:latest" >> /dev/null 2>&1
        cache_opt="--no-cache"
    fi

    docker build $cache_opt --file "build/Dockerfile.$comp" --platform linux/amd64 --tag "$tag" build/
done
