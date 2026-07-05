#!/usr/bin/env bash
#
# copy_agent_skills.sh
# Copies relevant SKILL.md files from ~/.gemini/config/skills/ into respective agent skill directories.

set -euo pipefail

# Determine source skills directory
SKILLS_SRC="$HOME/.gemini/config/skills"
if [ ! -d "$SKILLS_SRC" ]; then
    # Fallback to C:/Users/Fred/.gemini/config/skills for Windows bash environments
    SKILLS_SRC="/c/Users/Fred/.gemini/config/skills"
fi

if [ ! -d "$SKILLS_SRC" ]; then
    echo "Error: Skills source directory not found at $SKILLS_SRC"
    exit 1
fi

echo "Copying skills from $SKILLS_SRC..."

# Helper function to copy a skill
copy_skill() {
    local skill_name="$1"
    local target_agent="$2"
    local src_file="$SKILLS_SRC/$skill_name/SKILL.md"
    local dest_dir="app/agents/$target_agent/skills"
    local dest_file="$dest_dir/$skill_name.md"

    if [ -f "$src_file" ]; then
        mkdir -p "$dest_dir"
        cp "$src_file" "$dest_file"
        echo "  [+] Copied $skill_name -> $dest_file"
    else
        echo "  [-] Warning: Skill file $src_file not found."
    fi
}

# 1. Performance Agent Skills (Lead Architect)
echo ""
echo "=== Equipping Performance Agent ==="
for skill in \
    architecture-patterns \
    microservices-patterns \
    domain-modeling \
    api-design-principles \
    workflow-orchestration-patterns \
    event-store-design \
    python-design-patterns \
    async-python-patterns \
    postgresql-table-design \
    sql-optimization; do
    copy_skill "$skill" "performance"
done

# 2. Security Agent Skills
echo ""
echo "=== Equipping Security Agent ==="
for skill in \
    auth-implementation-patterns \
    secrets-management \
    security-requirement-extraction \
    python-error-handling; do
    copy_skill "$skill" "security"
done

# 3. SRE Agent Skills
echo ""
echo "=== Equipping SRE Agent ==="
for skill in \
    deployment-pipeline-design \
    gitops-workflow \
    grafana-dashboards \
    python-observability \
    python-resilience \
    cost-optimization \
    python-background-jobs \
    terraform-module-library; do
    copy_skill "$skill" "sre"
done

echo ""
echo "Skill distribution complete!"
