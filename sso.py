from typing import Optional, Type

from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command, web
from mautrix.types import EventType
from aiohttp.web import Request, Response, json_response

import json
import datetime
import re

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("command_aliases")
        helper.copy("admin_token")
        helper.copy("ak_url")
        helper.copy("flow_id")
        helper.copy("allowed_users")
        helper.copy("disallowed_users")
        helper.copy("expiration")
        helper.copy("message")

class Authentik(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    def get_command(self) -> str:
        return self.config['command_aliases'][0]

    def is_alias(self, command: str) -> bool:
        return command in self.config["command_aliases"]

    async def can_manage(self, evt: MessageEvent) -> bool:
        if (
                (len(self.config["allowed_users"]) > 0 and evt.sender not in self.config["allowed_users"]) \
                        or \
                (len(self.config["disallowed_users"]) > 0 and evt.sender in self.config["disallowed_users"])
            ):
            await evt.respond("You don't have permission to manage invitations.")
            return False
        else:
            return True

    def set_api_endpoints(self) -> None:
        self.config["api_url"] = self.config["ak_url"] + "/api/v3/stages/invitation/invitations/"

    def sanitize(self, username) -> str:
        sanitized_name = re.sub(r"[^a-zA-Z0-9]", '', username).lower()
        return sanitized_name

    @command.new(name=get_command, aliases=is_alias, help="Do things with the Authentik API", \
            require_subcommand=True)
    async def sso(self, evt: MessageEvent) -> None:
        pass

    @sso.subcommand("invite", help="Generate a new invitation link.")
    @command.argument("invitee", "invitee name", pass_raw=True, required=True)
    async def generate(self, evt: MessageEvent, invitee: str) -> None:
        await evt.mark_read()

        if not invitee:
            await evt.reply("please tell me who this invite is for")
            return

        if not await self.can_manage(evt):
            return

        self.set_api_endpoints()
        invitee = self.sanitize(invitee)

        ex_date = datetime.datetime.strftime( \
                (datetime.datetime.now() + datetime.timedelta(days=self.config["expiration"])), \
                "%Y-%m-%dT%H:%M")
        self.log.debug(f"DEBUG ex_date is set to {ex_date}")
        headers = {
            'Authorization': f"Bearer {self.config['admin_token']}",
            'Content-Type': 'application/json'
            }
        
        try:
            flow_id = self.config["flow_id"]
            response = await self.http.post(f"{self.config['api_url']}", headers=headers, \
                    json={"name": invitee, "fixed_data": {"attributes.notes": f"invited by {evt.sender}"}, "expires": ex_date, "single_use": True,
                          "flow": flow_id})
            status = response.status
            resp_json = await response.json()
            self.log.debug(f"DEBUG resp_json is: {resp_json}")
        except Exception as e:
            body = await response.text()
            await evt.respond(f"Uh oh! I got a {status} response from your registration endpoint:<br /> \
                        {body}<br /> \
                        which prompted me to produce this error:<br /> \
                        <code>{e.message}</code>", allow_html=True)
            return None
        try:
            token = resp_json['pk']
            slug = resp_json['flow_obj']['slug']
        except Exception as e:
            await evt.respond(f"I got a bad response back, sorry, something is borked. \n\
                    {resp_json}")
            self.log.exception(e)
            return None

        if self.config['message']:
            msg = self.config["message"].format(token=token, ak_url=self.config['ak_url'],
                    slug=slug, expiration=self.config['expiration'])
        else:
            msg = '<br />'.join(
                [
                    f"Invitation link created!",
                    f"",
                    f"Your unique url for registering is:",
                    f"{self.config['ak_url']}/if/flow/{slug}/?itoken={token}",
                    f"This invite will expire in {self.config['expiration']} days.",
                    f"If it expires before use, you must request a new invitation."
                ])

        room_participants = await self.client.get_joined_members(evt.room_id)

        if len(room_participants) > 2:
            r = await evt.reply("imma slide in2 ur DMs", allow_html=True)

            try:
                new_room = await self.client.create_room(
                    invitees=[evt.sender],
                    is_direct=True,
                    initial_state=[
                        {
                            "type": str(EventType.ROOM_NAME), 
                            "content": {"name": f"{invitee} - account registration link"}
                        }
                    ]
                )
                self.log.debug(f"DM created with {evt.sender} for {invitee}")

            except Exception as e:
                self.log.error(e)
                await evt.respond("snap, something went wrong, no cap.", edits=r)
                return

            try:
                await self.client.send_notice(new_room, html=msg)
                self.log.debug(f"Message sent to {evt.sender} for {invitee}")
            except Exception as e:
                self.log.error(e)
                await evt.respond("snap, something went wrong, no cap.", edits=r)
        else:
            await evt.reply(msg, allow_html=True)

    @web.get("/generate")
    async def web_generate_form(self, req: Request) -> Response:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Generate Invitation Link</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 20px auto;
                    padding: 0 20px;
                }
                .form-group {
                    margin-bottom: 20px;
                }
                input[type="text"] {
                    width: 100%;
                    padding: 8px;
                    margin-top: 5px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
                button {
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #45a049;
                }
                #result {
                    margin-top: 20px;
                    padding: 15px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    white-space: pre-wrap;
                    display: none;
                }
                .error {
                    color: #ff0000;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <h1>Generate Invitation Link</h1>
            <div class="form-group">
                <label for="invitee">Invitee Name:</label>
                <input type="text" id="invitee" name="invitee" required>
            </div>
            <button onclick="submitForm()">Generate Invitation</button>
            <div id="result"></div>
            <div id="error" class="error"></div>

            <script>
                async function submitForm() {
                    const invitee = document.getElementById('invitee').value;
                    const resultDiv = document.getElementById('result');
                    const errorDiv = document.getElementById('error');
                    
                    if (!invitee) {
                        errorDiv.textContent = 'Please enter an invitee name';
                        return;
                    }

                    try {
                        const response = await fetch(window.location.href, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                'invitee-name': invitee
                            })
                        });

                        const data = await response.json();
                        
                        if (response.ok) {
                            resultDiv.style.display = 'block';
                            resultDiv.textContent = data.message;
                            errorDiv.textContent = '';
                        } else {
                            errorDiv.textContent = data.error || 'An error occurred';
                            resultDiv.style.display = 'none';
                        }
                    } catch (error) {
                        errorDiv.textContent = 'Failed to submit form: ' + error;
                        resultDiv.style.display = 'none';
                    }
                }
            </script>
        </body>
        </html>
        """
        return Response(text=html, content_type='text/html')

    @web.post("/generate")
    async def web_generate(self, req: Request) -> Response:
        try:
            data = await req.json()
            invitee = data.get("invitee-name")
            sender = req.headers.get("X-authentik-username")

            if not invitee:
                return json_response({"error": "invitee-name is required"}, status=400)
            if not sender:
                return json_response({"error": "SSO authentication is required to use this endpoint"}, status=400)

            # Create a mock MessageEvent-like object
            class MockEvent:
                def __init__(self, sender):
                    self.sender = sender
                    self.room_id = None

                async def mark_read(self):
                    pass

                async def reply(self, msg, allow_html=True):
                    return msg

            mock_evt = MockEvent(sender)

            if not await self.can_manage(mock_evt):
                return json_response({"error": "User not authorized"}, status=403)

            self.set_api_endpoints()
            invitee = self.sanitize(invitee)

            ex_date = datetime.datetime.strftime(
                (datetime.datetime.now() + datetime.timedelta(days=self.config["expiration"])),
                "%Y-%m-%dT%H:%M")
            
            headers = {
                'Authorization': f"Bearer {self.config['admin_token']}",
                'Content-Type': 'application/json'
            }
            
            try:
                flow_id = self.config["flow_id"]
                response = await self.http.post(
                    f"{self.config['api_url']}", 
                    headers=headers,
                    json={
                        "name": invitee,
                        "fixed_data": {"attributes.notes": f"invited by {sender}"},
                        "expires": ex_date,
                        "single_use": True,
                        "flow": flow_id
                    }
                )
                status = response.status
                resp_json = await response.json()
            except Exception as e:
                return json_response({
                    "error": f"Failed to create invitation: {str(e)}"
                }, status=500)

            try:
                token = resp_json['pk']
                slug = resp_json['flow_obj']['slug']
            except Exception as e:
                return json_response({
                    "error": f"Invalid response from Authentik: {str(e)}"
                }, status=500)

            if self.config['message']:
                msg = self.config["message"].format(
                    token=token,
                    ak_url=self.config['ak_url'],
                    slug=slug,
                    expiration=self.config['expiration']
                )
            else:
                msg = '\n'.join([
                    "Invitation link created!",
                    "",
                    "Your unique url for registering is:",
                    f"{self.config['ak_url']}/if/flow/{slug}/?itoken={token}",
                    f"This invite will expire in {self.config['expiration']} days.",
                    "If it expires before use, you must request a new invitation."
                ])

            return json_response({
                "message": msg,
                "token": token,
                "url": f"{self.config['ak_url']}/if/flow/{slug}/?itoken={token}"
            })

        except Exception as e:
            return json_response({
                "error": f"Internal server error: {str(e)}"
            }, status=500)

    @sso.subcommand("list", help="List all invites that have been generated.")
    async def list(self, evt: MessageEvent) -> None:
        await evt.mark_read()

        if not await self.can_manage(evt):
            return

        self.set_api_endpoints()

        headers = {
            'Authorization': f"Bearer {self.config['admin_token']}"
            }

        try:
            response = await self.http.get(self.config['api_url'], headers=headers)
            resp_json = await response.json()
            invites = [i["name"] for i in resp_json['results']]
        except Exception as e:
            await evt.respond(f"request failed: {e.message}")
            return None
        
        # this isn't formatted nicely but i don't really care that much
        await evt.respond(f"<pre><code format=json>{invites}</code></pre>", allow_html=True)
