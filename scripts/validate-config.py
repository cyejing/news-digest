#!/usr/bin/env python3
"""
Configuration validation script for news-hotspots.

Validates sources.json, topics.json, topic-rules.json, and api-sources.json against JSON Schema and performs
additional consistency checks.

Usage:
    python3 validate-config.py [--defaults DEFAULTS_DIR] [--config CONFIG_DIR] [--verbose]
"""

import json
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any

try:
    from topic_utils import get_source_topic
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from topic_utils import get_source_topic

SOURCE_TYPES = ("rss", "twitter", "github", "reddit")

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def setup_logging(verbose: bool) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}")


def flatten_sources_data(sources_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert grouped sources config into the flat format used by validators."""
    grouped_sources = sources_data.get("sources", {})
    if not isinstance(grouped_sources, dict):
        raise ValueError("Invalid sources.json: expected 'sources' to be an object keyed by type")

    flattened = []
    for source_type, entries in grouped_sources.items():
        if not isinstance(entries, list):
            raise ValueError(
                f"Invalid sources.json: expected '{source_type}' sources to be an array"
            )
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Invalid sources.json: expected source entries under '{source_type}' to be objects"
                )
            normalized = entry.copy()
            normalized["type"] = normalized.get("type", source_type)
            flattened.append(normalized)
    return {"sources": flattened}


def group_sources_data(flat_sources: Dict[str, Any]) -> Dict[str, Any]:
    """Convert flat source list into grouped config shape for schema validation."""
    grouped = {source_type: [] for source_type in SOURCE_TYPES}
    for source in flat_sources.get("sources", []):
        source_type = source.get("type")
        if source_type not in grouped:
            raise ValueError(f"Invalid source type in merged config: {source_type}")
        grouped[source_type].append(source)
    return {"sources": grouped}


def validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any],
                          config_type: str) -> bool:
    """Validate data against JSON schema."""
    if not HAS_JSONSCHEMA:
        logging.warning("jsonschema not available, skipping schema validation")
        return True
        
    try:
        # Extract the relevant schema definition
        if config_type == "sources":
            schema_def = {
                "definitions": schema["definitions"],
                "type": "object",
                "required": ["sources"],
                "properties": {
                    "sources": schema["properties"]["sources"]
                }
            }
        elif config_type == "topics":
            schema_def = {
                "definitions": schema["definitions"],
                "type": "object",
                "required": ["topics"],
                "properties": {
                    "topics": schema["properties"]["topics"]
                }
            }
        elif config_type == "topic_rules":
            schema_def = {
                "definitions": schema["definitions"],
                "type": "object",
                "properties": {
                    "topic_rules": schema["properties"]["topic_rules"]
                },
            }
            data = {"topic_rules": data}
        elif config_type == "api_sources":
            schema_def = {
                "definitions": schema["definitions"],
                "type": "object",
                "required": ["api_sources"],
                "properties": {
                    "api_sources": schema["properties"]["api_sources"]
                },
            }
            data = {"api_sources": data}
        else:
            raise ValueError(f"Unknown config type: {config_type}")
            
        validate(instance=data, schema=schema_def)
        logging.info(f"✅ {config_type}.json passed schema validation")
        return True
        
    except ValidationError as e:
        logging.error(f"❌ Schema validation failed for {config_type}.json:")
        logging.error(f"   Path: {' -> '.join(str(p) for p in e.absolute_path)}")
        logging.error(f"   Error: {e.message}")
        return False


def validate_sources_consistency(sources_data: Dict[str, Any],
                               topics_data: Dict[str, Any],
                               topic_rules: Dict[str, Any]) -> bool:
    """Validate consistency between sources and topics."""
    errors = []
    
    # Get valid topic IDs
    valid_topics = {topic["id"] for topic in topics_data["topics"]}
    logging.debug(f"Valid topic IDs: {valid_topics}")
    
    flat_sources = flatten_sources_data(sources_data)["sources"]

    # Check source topic references
    for source in flat_sources:
        source_id = source.get("id", "unknown")
        source_topic = get_source_topic(source, rules=topic_rules)
        
        # Check for invalid topic references
        if source_topic and source_topic not in valid_topics:
            errors.append(f"Source '{source_id}' references invalid topic: {source_topic}")
            
        if not source_topic:
            errors.append(f"Source '{source_id}' has no topic assigned")
            
    # Check for duplicate source IDs
    source_ids = [source.get("id") for source in flat_sources]
    duplicates = {id for id in source_ids if source_ids.count(id) > 1}
    if duplicates:
        errors.append(f"Duplicate source IDs found: {duplicates}")
        
    # Check for duplicate topic IDs
    topic_ids = [topic.get("id") for topic in topics_data["topics"]]
    duplicates = {id for id in topic_ids if topic_ids.count(id) > 1}
    if duplicates:
        errors.append(f"Duplicate topic IDs found: {duplicates}")
        
    if errors:
        logging.error("❌ Consistency validation failed:")
        for error in errors:
            logging.error(f"   {error}")
        return False
    else:
        logging.info("✅ Consistency validation passed")
        return True


def validate_topic_rules_consistency(topic_rules: Dict[str, Any], topics_data: Dict[str, Any]) -> bool:
    """Validate topic-rules references against the topic taxonomy."""
    valid_topics = {topic["id"] for topic in topics_data["topics"]}
    errors = []

    for topic_id in topic_rules.get("topic_priority", []):
        if topic_id not in valid_topics:
            errors.append(f"topic_priority contains invalid topic: {topic_id}")

    for legacy_id, mapped_id in (topic_rules.get("legacy_topic_map") or {}).items():
        if mapped_id not in valid_topics:
            errors.append(f"legacy_topic_map[{legacy_id!r}] points to invalid topic: {mapped_id}")

    v2ex_rules = (topic_rules.get("source_rules", {}) or {}).get("v2ex", {})
    for mapping_name in ("node_topic_map", "keyword_map"):
        mapping = v2ex_rules.get(mapping_name, {})
        if not isinstance(mapping, dict):
            continue
        for source_key, topic_ids in mapping.items():
            if not isinstance(topic_ids, list):
                continue
            for topic_id in topic_ids if mapping_name == "node_topic_map" else [source_key]:
                if topic_id not in valid_topics:
                    errors.append(f"v2ex {mapping_name} references invalid topic: {topic_id}")

    if errors:
        logging.error("❌ Topic rules consistency validation failed:")
        for error in errors:
            logging.error(f"   {error}")
        return False

    logging.info("✅ Topic rules consistency validation passed")
    return True


def validate_topic_search_fields(topics_data: Dict[str, Any]) -> bool:
    """Validate topic-level search query fields."""
    errors = []
    for topic in topics_data.get("topics", []):
        if not isinstance(topic, dict):
            continue
        topic_id = topic.get("id", "unknown")
        search = topic.get("search", {})
        if not isinstance(search, dict):
            errors.append(f"Topic '{topic_id}' has invalid search block")
            continue
        for key in ("google_queries", "twitter_queries", "reddit_queries", "github_queries", "exclude"):
            if key in search and not isinstance(search.get(key), list):
                errors.append(f"Topic '{topic_id}' search.{key} must be an array")

    if errors:
        logging.error("❌ Topic search-field validation failed:")
        for error in errors:
            logging.error(f"   {error}")
        return False

    logging.info("✅ Topic search-field validation passed")
    return True


def validate_api_sources_consistency(api_sources: Dict[str, Any], topics_data: Dict[str, Any]) -> bool:
    """Validate API source topic references against the topic taxonomy."""
    valid_topics = {topic["id"] for topic in topics_data["topics"]}
    errors = []
    source_ids = []

    for source in api_sources.get("sources", []):
        source_id = source.get("id")
        if source_id:
            source_ids.append(source_id)
        source_topic = source.get("topic")
        if source_topic not in valid_topics:
            errors.append(f"API source '{source_id}' references invalid topic: {source_topic}")

    duplicates = {item for item in source_ids if source_ids.count(item) > 1}
    if duplicates:
        errors.append(f"Duplicate API source IDs found: {duplicates}")

    if errors:
        logging.error("❌ API sources consistency validation failed:")
        for error in errors:
            logging.error(f"   {error}")
        return False

    logging.info("✅ API sources consistency validation passed")
    return True


def validate_source_types(sources_data: Dict[str, Any]) -> bool:
    """Validate source-type specific requirements."""
    errors = []
    
    flat_sources = flatten_sources_data(sources_data)["sources"]

    for source in flat_sources:
        source_id = source.get("id", "unknown")
        source_type = source.get("type")
        
        if source_type == "rss":
            if not source.get("url"):
                errors.append(f"RSS source '{source_id}' missing required 'url' field")
        elif source_type == "twitter":
            if not source.get("handle") and not source.get("query") and not source.get("search_query"):
                errors.append(
                    f"Twitter source '{source_id}' missing required 'handle' or 'query/search_query' field"
                )
        elif source_type == "github":
            if not source.get("repo"):
                errors.append(f"GitHub source '{source_id}' missing required 'repo' field")
        elif source_type == "reddit":
            if not source.get("subreddit") and not source.get("query") and not source.get("search_query"):
                errors.append(
                    f"Reddit source '{source_id}' missing required 'subreddit' or 'query/search_query' field"
                )
        else:
            errors.append(f"Source '{source_id}' has invalid type: {source_type}")
            
    if errors:
        logging.error("❌ Source type validation failed:")
        for error in errors:
            logging.error(f"   {error}")
        return False
    else:
        logging.info("✅ Source type validation passed")
        return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate news-hotspots configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 validate-config.py
    python3 validate-config.py --defaults config/defaults --config workspace/config --verbose
    """
    )
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults"), help="Default configuration directory with skill defaults (default: config/defaults)")
    parser.add_argument("--config", type=Path, help="User configuration directory for overlays (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


def main():
    """Main validation function."""
    args = parse_args()
    logger = setup_logging(args.verbose)

    # Load config_loader for merged configurations
    try:
        from config_loader import (
            load_merged_api_sources,
            load_merged_sources,
            load_merged_topics,
            load_merged_topic_rules,
        )
    except ImportError:
        # Fallback for relative import
        import sys
        sys.path.append(str(Path(__file__).parent))
        from config_loader import (
            load_merged_api_sources,
            load_merged_sources,
            load_merged_topics,
            load_merged_topic_rules,
        )
    
    # File paths
    schema_path = Path("config/schema.json")
    
    if args.config:
        logger.info(f"Validating merged configuration: defaults={args.defaults}, config={args.config}")
    else:
        logger.info(f"Validating default configuration: {args.defaults}")
    
    try:
        defaults_dir = args.defaults
        config_dir = args.config
        
        # Load schema
        schema = load_json_file(schema_path)
        logger.debug("Loaded schema.json")
        
        # Load merged configuration data
        merged_sources = load_merged_sources(defaults_dir, config_dir)
        merged_topics = load_merged_topics(defaults_dir, config_dir)
        merged_topic_rules = load_merged_topic_rules(defaults_dir, config_dir)
        merged_api_sources = {"sources": load_merged_api_sources(defaults_dir, config_dir)}

        # Convert to the format expected by validation functions
        sources_data = group_sources_data({"sources": merged_sources})
        topics_data = {"topics": merged_topics}
        
        logger.debug(f"Loaded {len(merged_sources)} merged sources, {len(merged_topics)} merged topics")
        
        # Perform validations
        all_valid = True
        
        # Schema validation
        all_valid &= validate_against_schema(sources_data, schema, "sources")
        all_valid &= validate_against_schema(topics_data, schema, "topics")
        all_valid &= validate_against_schema(merged_topic_rules, schema, "topic_rules")
        all_valid &= validate_against_schema(merged_api_sources, schema, "api_sources")

        # Consistency validation
        all_valid &= validate_sources_consistency(sources_data, topics_data, merged_topic_rules)
        all_valid &= validate_topic_rules_consistency(merged_topic_rules, topics_data)
        all_valid &= validate_topic_search_fields(topics_data)
        all_valid &= validate_api_sources_consistency(merged_api_sources, topics_data)
        
        # Source type validation  
        all_valid &= validate_source_types(sources_data)
        
        # Summary
        if all_valid:
            logger.info("🎉 All validations passed!")
            return 0
        else:
            logger.error("💥 Validation failed!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Validation error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
