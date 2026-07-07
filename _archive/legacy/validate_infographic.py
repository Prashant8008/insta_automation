"""
validate_infographic.py
Phase 2.5b — Post-processing validation. Runs after generate_instagram_posts.py,
before build_instagram_visuals.cjs. Recomputes ALL bar percentages in Python
(never trusts Gemini's math) and drops any bar whose raw_value has no match
in verified_facts_today.json. Supports template-specific validation for
STATUS_BREAKDOWN, BEFORE_AFTER, SINGLE_SPOTLIGHT, and TIMELINE.
"""
import json, os, re

INFOGRAPHIC_INPUT = "infographic_data.json"
VERIFIED_FACTS_PATH = "verified_facts_today.json"
VALIDATED_OUTPUT = "infographic_data.validated.json"
MATCH_TOLERANCE = 0.001

class ValidationError(Exception):
    pass

def normalize_tag(tag):
    tag = tag.lower()
    if any(x in tag for x in ["navy", "naval", "marine", "maritime", "inas", "ins"]):
        return "navy"
    if any(x in tag for x in ["helicopter", "seahawk", "mh-60r", "dhruv", "chetak", "sea king", "chopper"]):
        return "helicopter"
    if any(x in tag for x in ["army", "infantry", "military"]):
        return "army"
    if any(x in tag for x in ["air force", "iaf", "fighter", "jet", "aircraft", "tejas", "sukhoi"]):
        return "air_force"
    if any(x in tag for x in ["missile", "vshorads", "brahmos", "akash"]):
        return "missile"
    return tag

def _find_matching_fact(raw_value, topic_tags, verified_facts):
    for fact in verified_facts:
        if abs(fact["value"] - raw_value) <= MATCH_TOLERANCE:
            if not topic_tags or not fact.get("topic_tags"):
                return fact
            # Normalize fact tags and topic tags
            fact_tags_norm = {normalize_tag(t) for t in fact["topic_tags"] if t}
            topic_tags_norm = {normalize_tag(t) for t in topic_tags if t}
            # Direct overlap check of normalized tags
            if fact_tags_norm & topic_tags_norm:
                return fact
    return None

def normalize_bars(bars, chart_type):
    if not bars:
        return bars
    raw_values = [b["raw_value"] for b in bars]
    if chart_type == "part_of_whole":
        total = sum(raw_values)
        if total <= 0:
            raise ValidationError("part_of_whole chart has zero/negative total")
        for b in bars:
            b["value"] = f"{(b['raw_value'] / total) * 100:.0f}%"
    elif chart_type == "relative_max":
        max_val = max(raw_values)
        if max_val <= 0:
            raise ValidationError("relative_max chart has zero/negative max")
        for b in bars:
            b["value"] = f"{(b['raw_value'] / max_val) * 100:.0f}%"
    else:
        raise ValidationError(f"Unknown chart_type '{chart_type}'")
    for b in bars:
        if float(b["value"].rstrip("%")) > 100:
            raise ValidationError(f"Bar '{b['label']}' exceeded 100% after normalization")
    return bars

def validate_and_source_bars(bars, topic_tags, verified_facts):
    kept, dropped = [], []
    for b in bars:
        fact = _find_matching_fact(b["raw_value"], topic_tags, verified_facts)
        if fact is None:
            dropped.append(b["label"])
            continue
        b["source"] = fact["source"]
        b["source_url"] = fact["url"]
        kept.append(b)
    if dropped:
        print(f"[validate_infographic] Dropped unsourced bars: {dropped}")
    return kept

def _extract_numbers(text):
    if not text:
        return []
    # Find float and integer numbers in text strings
    matches = re.findall(r"(?<![\d./])(\d+(?:\.\d+)?)(?!\d)", text)
    nums = []
    for m in matches:
        try:
            nums.append(float(m) if "." in m else int(m))
        except ValueError:
            pass
    return nums

def validate_infographic(infographic_data, verified_facts):
    topic_tags = infographic_data.get("topic_tags", [])
    template = infographic_data.get("visual_template", "STATUS_BREAKDOWN").upper()
    
    if template == "STATUS_BREAKDOWN":
        chart_type = infographic_data.get("chart_type")
        if not chart_type:
            raise ValidationError("STATUS_BREAKDOWN missing 'chart_type' field")
        bars = validate_and_source_bars(infographic_data.get("bars", []), topic_tags, verified_facts)
        if not bars:
            raise ValidationError("All bars dropped for lack of verified sourcing — do not render this post")
        infographic_data["bars"] = normalize_bars(bars, chart_type)
        used_sources = sorted(set(b["source"] for b in bars))
        infographic_data["source"] = f"Source: {', '.join(used_sources)} | @ssb.connect"
        
    elif template == "BEFORE_AFTER":
        before_val_str = infographic_data.get("before_value", "")
        after_val_str = infographic_data.get("after_value", "")
        before_nums = _extract_numbers(before_val_str)
        after_nums = _extract_numbers(after_val_str)
        all_nums = before_nums + after_nums
        
        matched_sources = []
        for val in all_nums:
            fact = _find_matching_fact(val, topic_tags, verified_facts)
            if fact:
                matched_sources.append(fact["source"])
                
        if not matched_sources:
            raise ValidationError("BEFORE_AFTER comparison contains no verified numbers matching the facts pool")
            
        infographic_data["source"] = f"Source: {', '.join(sorted(set(matched_sources)))} | @ssb.connect"
        
    elif template == "SINGLE_SPOTLIGHT":
        stat_str = infographic_data.get("spotlight_stat", "")
        stat_nums = _extract_numbers(stat_str)
        if not stat_nums:
            raise ValidationError("SINGLE_SPOTLIGHT missing numeric spotlight_stat")
            
        matched_sources = []
        for val in stat_nums:
            fact = _find_matching_fact(val, topic_tags, verified_facts)
            if fact:
                matched_sources.append(fact["source"])
                
        if not matched_sources:
            raise ValidationError(f"Spotlight stat '{stat_str}' could not be matched to a verified fact in the pool")
            
        infographic_data["source"] = f"Source: {', '.join(sorted(set(matched_sources)))} | @ssb.connect"
        
    elif template == "TIMELINE":
        timeline_items = infographic_data.get("timeline", [])
        if not timeline_items:
            raise ValidationError("TIMELINE template has no items in 'timeline' array")
            
        matched_sources = []
        for item in timeline_items:
            item_text = f"{item.get('date', '')} {item.get('title', '')} {item.get('desc', '')}"
            item_nums = _extract_numbers(item_text)
            for val in item_nums:
                fact = _find_matching_fact(val, topic_tags, verified_facts)
                if fact:
                    matched_sources.append(fact["source"])
                    
        if not matched_sources:
            raise ValidationError("TIMELINE template has no events matched to a verified fact in the pool")
            
        infographic_data["source"] = f"Source: {', '.join(sorted(set(matched_sources)))} | @ssb.connect"
        
    else:
        raise ValidationError(f"Unknown visual_template '{template}'")
        
    return infographic_data

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=None)
    args = parser.parse_args()

    input_file = INFOGRAPHIC_INPUT
    output_file = VALIDATED_OUTPUT
    if args.index is not None:
        input_file = f"infographic_data_{args.index}.json"
        output_file = f"infographic_data.validated_{args.index}.json"

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"{input_file} not found")
    if not os.path.exists(VERIFIED_FACTS_PATH):
        raise FileNotFoundError(f"{VERIFIED_FACTS_PATH} not found — run extract_verified_facts.py first")
    with open(input_file, "r", encoding="utf-8") as f:
        infographic_data = json.load(f)
    with open(VERIFIED_FACTS_PATH, "r", encoding="utf-8") as f:
        verified_facts = json.load(f)
    try:
        validated = validate_infographic(infographic_data, verified_facts)
    except ValidationError as e:
        print(f"[validate_infographic] {input_file} REJECTED: {e}")
        raise SystemExit(1)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(validated, f, indent=2)
    print(f"[validate_infographic] {input_file} PASSED -> {output_file}")

if __name__ == "__main__":
    main()
