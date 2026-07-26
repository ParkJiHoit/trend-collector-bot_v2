import notion_api


def parse_settings_response(response):
    rows = []
    for item in response["results"]:
        props = item["properties"]
        title_parts = props["키워드"]["title"]
        keyword = title_parts[0]["plain_text"] if title_parts else ""
        select = props["버티컬"]["select"]
        rows.append(
            {
                "keyword": keyword,
                "vertical": select["name"] if select else None,
                "rss_url": props["RSS피드URL"]["url"],
                "active": props["활성여부"]["checkbox"],
            }
        )
    return rows


def load_settings(database_id, token):
    response = notion_api.query_database(database_id, token)
    rows = parse_settings_response(response)
    return [row for row in rows if row["active"]]
