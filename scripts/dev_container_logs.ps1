param(
    [switch]$Follow
)

$ErrorActionPreference = "Stop"

if ($Follow) {
    docker compose logs -f mcp
    exit 0
}

docker compose logs mcp
