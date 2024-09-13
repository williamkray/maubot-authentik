from typing import Optional, Type

from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command

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

        await evt.respond(msg, allow_html=True)

#   @sso.subcommand("status", help="Return the status of an invite token.")
#   @command.argument("token", "Token", pass_raw=True, required=True)
#   async def status(self, evt: MessageEvent, token: str) -> None:
#       await evt.mark_read()

#       if not await self.can_manage(evt):
#           return

#       self.set_api_endpoints()

#       if not token:
#           await evt.respond("you must supply a token to check")

#       headers = {
#           'Authorization': f"SharedSecret {self.config['admin_secret']}",
#           'Content-Type': 'application/json'
#           }

#       try:
#           response = await self.http.get(f"{self.config['api_url']}/token/{token}", headers=headers)
#           resp_json = await response.json()
#       except Exception as e:
#           await evt.respond(f"request failed: {e.message}")
#           return None
#       
#       # this isn't formatted nicely but i don't really care that much
#       await evt.respond(f"Status of token {token}: \n<pre><code format=json>{json.dumps(resp_json, indent=4)}</code></pre>", allow_html=True)

#   @sso.subcommand("revoke", help="Disable an existing invite token.")
#   @command.argument("token", "Token", pass_raw=True, required=True)
#   async def revoke(self, evt: MessageEvent, token: str) -> None:
#       await evt.mark_read()

#       if not await self.can_manage(evt):
#           return

#       self.set_api_endpoints()

#       if not token:
#           await evt.respond("you must supply a token to revoke")

#       headers = {
#           'Authorization': f"SharedSecret {self.config['admin_secret']}",
#           'Content-Type': 'application/json'
#           }

#       # this is a really gross way of handling legacy installs and should be cleaned up
#       # basically this command used to use PUT but now uses PATCH
#       if self.config["legacy_mr"] == True:
#           try:
#               response = await self.http.put(f"{self.config['api_url']}/token/{token}", headers=headers, \
#                       json={"disable": True})
#               resp_json = await response.json()
#           except Exception as e:
#               await evt.respond(f"request failed: {e.message}")
#               return None
#       else:
#           try:
#               response = await self.http.patch(f"{self.config['api_url']}/token/{token}", headers=headers, \
#                       json={"disabled": True})
#               resp_json = await response.json()
#           except Exception as e:
#               await evt.respond(f"request failed: {e.message}")
#               return None
#       
#       # this isn't formatted nicely but i don't really care that much
#       await evt.respond(f"<pre><code format=json>{json.dumps(resp_json, indent=4)}</code></pre>", allow_html=True)

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
