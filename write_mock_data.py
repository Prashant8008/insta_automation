import json

def main():
    carousel = {
      "1": { "HEADER_LABEL": "GROWTH LOOP", "HOOK_PART_1": "How they grew", "HOOK_PART_2": "to 100k users", "HOOK_EMPHASIS": "rapidly", "SUBTITLE": "A simple workflow change that unlocked double digit conversion rates." },
      "2": { "PILL_LABEL": "THE PROBLEM", "EYEBROW": "Conversion", "HEADLINE_PART_1": "Friction on entry", "HEADLINE_PART_2": "causes users to", "HEADLINE_EMPHASIS": "drop", "SUBHEAD": "Demanding credentials early destroys user interest.", "BODY_TEXT": "When sign-up is required before seeing value, 90% of users bounce immediately." },
      "3": { "HEADER_LABEL": "THE STAT", "HUGE_STAT": "90%", "CIRCLE_WORD_1": "USERS", "CIRCLE_WORD_2": "BOUNCED", "HEADLINE_PART_1": "Requiring signup", "HEADLINE_PART_2": "too early leaks", "HEADLINE_EMPHASIS": "revenue", "BODY_TEXT": "The initial signup wall was the single biggest drop-off point in the user journey." },
      "4": { "PILL_LABEL": "THE SHIFT", "EYEBROW": "Frictionless", "HEADLINE_PART_1": "Delivering value", "HEADLINE_PART_2": "before presenting the", "HEADLINE_EMPHASIS": "paywall", "SUBHEAD": "Give them a taste of the features first.", "BODY_TEXT": "They postponed the signup prompt until after the user completed their first task." },
      "5": { "HEADER_LABEL": "THE RESULT", "HUGE_STAT": "5x", "CIRCLE_WORD_1": "SALES", "CIRCLE_WORD_2": "JUMP", "HEADLINE_PART_1": "Revenue boosted", "HEADLINE_PART_2": "five times in a", "HEADLINE_EMPHASIS": "week", "BODY_TEXT": "Conversion rose from 1% to 5% after removing early authentication requirements." },
      "6": { "HEADER_LABEL": "THE TAKEAWAY", "HUGE_STAT": "80%", "HEADLINE_PART_1": "Simplification of UX", "HEADLINE_PART_2": "wins the user retention", "HEADLINE_EMPHASIS": "battle", "SUBHEAD": "Focus on removing steps, not adding features.", "BODY_TEXT": "The easiest way to boost your conversion is to shorten the distance to first value." },
      "7": { "HEADLINE_PART_1": "Optimize your onboarding", "HEADLINE_PART_2": "to multiply", "HEADLINE_EMPHASIS": "conversions", "SUBHEAD": "Remove friction today. Follow @founderswing for more insights." }
    }

    spotlight = {
      "1": { "HEADER_LABEL": "TOOL SPOTLIGHT", "HOOK_PART_1": "This AI workflow", "HOOK_PART_2": "will save you", "HOOK_EMPHASIS": "hours", "SUBTITLE": "How to automate tedious summarization tasks using simple API pipes." },
      "2": { "PILL_LABEL": "THE SETUP", "EYEBROW": "Data Fetch", "HEADLINE_PART_1": "Pull news updates", "HEADLINE_PART_2": "from RSS feeds", "HEADLINE_EMPHASIS": "instantly", "BODY_TEXT": "Use automated scraper scripts to monitor industry developments in real-time." },
      "3": { "PILL_LABEL": "THE PROCESS", "EYEBROW": "Filtering", "HEADLINE_PART_1": "Filter out noise", "HEADLINE_PART_2": "using LLM semantic", "HEADLINE_EMPHASIS": "checks", "BODY_TEXT": "Prompt the model to retain only high-impact developments." },
      "4": { "PILL_LABEL": "THE ACTION", "EYEBROW": "Delivery", "HEADLINE_PART_1": "Deliver structured", "HEADLINE_PART_2": "posts directly to your", "HEADLINE_EMPHASIS": "queue", "BODY_TEXT": "Connect to Slack or publishing webhooks to post with one click." },
      "5": { "HEADLINE_PART_1": "Deploy the pipeline", "HEADLINE_PART_2": "to reclaim your", "HEADLINE_EMPHASIS": "time", "SUBHEAD": "Link in bio to download the script. Follow @founderswing." }
    }

    infographic = {
      "title_main": "AI Adoption Rates by",
      "title_span": "Department",
      "subtitle": "Percentage of enterprises that have integrated generative AI in daily tasks (2026)",
      "badge": "📊 Enterprise Stats",
      "date_label": "July 2026 Report",
      "takeaway_num": "84%",
      "takeaway_text": "of marketing departments lead the integration of AI tools.",
      "source": "Source: McKinsey & Company | @founderswing",
      "bars": [
        { "label": "Marketing & Creative", "value": "84%", "color": "#E63946" },
        { "label": "Customer Operations", "value": "72%", "color": "#D9785B" },
        { "label": "Software Engineering", "value": "65%", "color": "#E8A33D" },
        { "label": "Product Development", "value": "58%", "color": "#5E6AD2" },
        { "label": "Sales & Support", "value": "45%", "color": "#5A5A5A" }
      ]
    }

    poll = {
      "badge": "💬 COMMUNITY POLL",
      "question_part_1": "What is the biggest bottleneck in your",
      "question_emphasis": "workflow?",
      "option_a": "Finding high-quality datasets",
      "option_b": "Writing copy manually",
      "option_c": "Designing visual layouts",
      "option_d": "Scheduling and deployment"
    }

    with open("./carousel_data.json", "w") as f:
        json.dump(carousel, f, indent=2)
    with open("./spotlight_data.json", "w") as f:
        json.dump(spotlight, f, indent=2)
    with open("./infographic_data.json", "w") as f:
        json.dump(infographic, f, indent=2)
    with open("./poll_data.json", "w") as f:
        json.dump(poll, f, indent=2)
        
    print("Mock JSON data written successfully.")

if __name__ == "__main__":
    main()
