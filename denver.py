from flask import Flask, request
from slack import WebClient
from slack.errors import SlackApiError
from confluence import Api
import os
from github import Github

from flask import Flask, request, jsonify
from slack import WebClient
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json

app = Flask(__name__)

# Initialize Slack API client
slack_token = os.environ.get('SLACK_TOKEN')
slack_client = WebClient(token=slack_token)

# Initialize Confluence API client
confluence_base_url = os.environ.get('CONFLUENCE_BASE_URL')
confluence_api_token = os.environ.get('CONFLUENCE_API_TOKEN')
confluence = Api(url=confluence_base_url, username='', password=confluence_api_token)

# Endpoint to receive Slack events
@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.json
    if data['type'] == 'event_callback' and 'text' in data['event']:
        try:
            command = data['event']['text']
            if command == 'get_confluence_data':
                page_id = '12345'
                try:
                    # Fetch Confluence page content
                    confluence_data = confluence.get(f'/rest/api/content/{page_id}')
                    # Send Confluence data to Slack
                    slack_client.chat_postMessage(channel=data['event']['channel'], text=str(confluence_data))
                except Exception as confluence_error:
                    return str(confluence_error), 500  # Handle Confluence API error
        except Exception as e:
            return str(e), 500  # Handle other errors
    return '', 200

@app.route('/slack/fetch-confluence', methods=['POST'])
def slack_command():
    try:
        command = request.form.get('text')
        # Retrieve documents with relevant metadata from Confluence
        relevant_documents = fetch_documents_with_metadata(command)
        # Send the list of documents to Slack
        slack_client.chat_postMessage(channel=request.form.get('channel_id'), text=str(relevant_documents))
    except Exception as e:
        return str(e), 500  # Handle errors

    return '', 200

def fetch_documents_with_metadata(metadata):
    # Example: Fetch Confluence pages with specified metadata
    # Replace this with your logic to query Confluence using python-confluence
    pages_with_metadata = confluence.get('/rest/api/content', params={'metadata': metadata})
    return pages_with_metadata

if __name__ == '__main__':
    app.run()


# ----------------
# GitHub API setup
github_token = os.environ.get('GITHUB_TOKEN')
headers = {
    'Authorization': f'Bearer {github_token}',
    'Accept': 'application/vnd.github.v3+json'
}

github_token = os.environ.get('GITHUB_TOKEN')
github_client = Github(github_token)
# Slack command to fetch GitHub data
@app.route('/slack/github-integration', methods=['POST'])
def github_integration():
    try:
        # Fetch latest pull requests, issues, and READMEs
        prs = fetch_latest_prs()
        issues = fetch_latest_issues()
        readmes = fetch_latest_readmes()

        # Send the data to Slack
        response_text = f"Latest PRs:\n{prs}\n\nLatest Issues:\n{issues}\n\nLatest READMEs:\n{readmes}"
        slack_client.chat_postMessage(channel=request.form.get('channel_id'), text=response_text)
    except Exception as e:
        return str(e), 500  # Handle errors

    return '', 200

def fetch_latest_prs():
    # Example: Fetch latest pull requests from your GitHub organization
    organization = github_client.get_organization('your-organization')
    prs = organization.get_pulls(state='open', sort='created', direction='desc')
    pr_titles = [pr.title for pr in prs]
    return "\n".join(pr_titles)

def fetch_latest_issues():
    # Example: Fetch latest issues from your GitHub organization
    organization = github_client.get_organization('your-organization')
    issues = organization.get_issues(state='open', sort='created', direction='desc')
    issue_titles = [issue.title for issue in issues]
    return "\n".join(issue_titles)

def fetch_latest_readmes():
    # Example: Fetch latest READMEs from your GitHub organization's repositories
    organization = github_client.get_organization('your-organization')
    repos = organization.get_repos()
    readmes = []
    for repo in repos:
        readme = repo.get_readme()
        readmes.append(f"{repo.name}:\n{readme.decoded_content.decode('utf-8')}")
    return "\n".join(readmes)


# --- SLACK interaction setup
# Store user tokens (temporary solution, use a proper database in production)
user_tokens = {}

# Slack command to start authentication process
@app.route('/slack/auth-popup', methods=['POST'])
def auth_popup():
    try:
        trigger_id = request.form.get('trigger_id')

        # Open an interactive pop-up
        slack_client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "auth_modal",
                "title": {
                    "type": "plain_text",
                    "text": "Authentication"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Enter your authentication tokens for each service:"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "google_drive",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "google_drive_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Google Drive Token"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "github",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "github_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "GitHub Token"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "confluence",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "confluence_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Confluence Token"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Authorize"
                                },
                                "style": "primary",
                                "action_id": "authorize"
                            }
                        ]
                    }
                ]
            }
        )
    except Exception as e:
        return str(e), 500  # Handle errors

    return '', 200

# Handle interactive message actions
@app.route('/slack/actions', methods=['POST'])
def handle_actions():
    try:
        payload = request.form.get('payload')
        payload_dict = json.loads(payload)
        action_id = payload_dict['actions'][0]['action_id']

        if action_id == 'authorize':
            user_id = payload_dict['user']['id']
            google_drive_token = payload_dict['view']['state']['values']['google_drive']['google_drive_input']['value']
            github_token = payload_dict['view']['state']['values']['github']['github_input']['value']
            confluence_token = payload_dict['view']['state']['values']['confluence']['confluence_input']['value']
            
            user_tokens[user_id] = {
                'google_drive': google_drive_token,
                'github': github_token,
                'confluence': confluence_token
            }

            response_text = "Tokens authorized!"
            slack_client.chat_postMessage(channel=payload_dict['user']['id'], text=response_text)

    except Exception as e:
        return str(e), 500  # Handle errors

    return '', 200

if __name__ == '__main__':
    app.run()


