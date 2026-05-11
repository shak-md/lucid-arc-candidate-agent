"""
Adaptive Card payloads for Teams bot responses.
Cards render rich, structured UI inside Teams chat.
All cards follow the Adaptive Card 1.5 schema.
"""


def pool_selection_card(pools: list[dict], candidate_count: int, filename: str) -> dict:
    """Card with a dropdown to choose a candidate pool and a submit button."""
    choices = [
        {"title": p["pool_name"], "value": p["pool_id"]}
        for p in pools
    ]
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Candidate Pool Selection",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "TextBlock",
                "text": f"Found **{candidate_count}** valid candidates in **{filename}**. Select a pool to add them to.",
                "wrap": True,
            },
            {
                "type": "Input.ChoiceSet",
                "id": "selected_pool_id",
                "style": "compact",
                "isRequired": True,
                "errorMessage": "Please select a pool.",
                "placeholder": "Choose a candidate pool...",
                "choices": choices,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Select Pool",
                "data": {"action": "pool_selected"},
            }
        ],
    }


def confirmation_card(pool_name: str, candidate_count: int) -> dict:
    """Card asking the recruiter to confirm or cancel the load."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Confirm Candidate Load",
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Pool", "value": pool_name},
                    {"title": "Candidates", "value": str(candidate_count)},
                ],
            },
            {
                "type": "TextBlock",
                "text": "This will add the candidates to the selected pool in Workday. Do you want to proceed?",
                "wrap": True,
                "color": "Warning",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Confirm",
                "style": "positive",
                "data": {"action": "confirm"},
            },
            {
                "type": "Action.Submit",
                "title": "Cancel",
                "style": "destructive",
                "data": {"action": "cancel"},
            },
        ],
    }


def validation_error_card(invalid_records: list[dict]) -> dict:
    """Card listing row-level validation errors."""
    rows = [
        {
            "type": "TextBlock",
            "text": f"Row {e['row_number']} - **{e['field']}**: {e['reason']}",
            "wrap": True,
            "color": "Attention",
            "spacing": "Small",
        }
        for e in invalid_records[:20]
    ]

    if len(invalid_records) > 20:
        rows.append({
            "type": "TextBlock",
            "text": f"...and {len(invalid_records) - 20} more errors.",
            "wrap": True,
            "isSubtle": True,
        })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Validation Errors Found",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Attention",
            },
            {
                "type": "TextBlock",
                "text": "Please fix the following issues and re-upload your file.",
                "wrap": True,
            },
            *rows,
        ],
    }


def success_card(pool_name: str, succeeded: int, failed: int) -> dict:
    """Card showing the result of a successful (or partially successful) load."""
    status_color = "Good" if failed == 0 else "Warning"
    status_text = (
        f"All {succeeded} candidates added successfully."
        if failed == 0
        else f"{succeeded} added, {failed} failed. Review the failed records and resubmit."
    )

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Load Complete",
                "weight": "Bolder",
                "size": "Medium",
                "color": status_color,
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Pool", "value": pool_name},
                    {"title": "Succeeded", "value": str(succeeded)},
                    {"title": "Failed", "value": str(failed)},
                ],
            },
            {
                "type": "TextBlock",
                "text": status_text,
                "wrap": True,
                "color": status_color,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Load Another File",
                "data": {"action": "restart"},
            }
        ],
    }
