import logging
from typing import List, Optional

from llmagent.agent.chat_agent import ChatAgent, ChatAgentConfig
from llmagent.agent.chat_document import (
    ChatDocAttachment,
    ChatDocMetaData,
    ChatDocument,
    Entity,
)

logger = logging.getLogger(__name__)
# TODO - this is currently hardocded to validate the TO:<recipient> format
# but we could have a much more general declarative grammar-based validator


class ValidatorAgentConfig(ChatAgentConfig):
    recipients: List[str]
    tool_recipient: str


class ValidatorAttachment(ChatDocAttachment):
    content: str = ""


class ValidatorAgent(ChatAgent):
    def __init__(self, config: ValidatorAgentConfig):
        super().__init__(config)
        self.config: ValidatorAgentConfig = config
        self.llm = None
        self.vecdb = None

    def user_response(
        self,
        msg: Optional[str | ChatDocument] = None,
    ) -> Optional[ChatDocument]:
        # don't get user input
        return None

    def agent_response(
        self,
        msg: Optional[str | ChatDocument] = None,
    ) -> Optional[ChatDocument]:
        """
        Check whether the incoming message is in the expected format.
        Used to check whether the output of the LLM of the calling agent is
        in the expected format.

        Args:
            msg (str|ChatDocument): the incoming message (pending message of the task)

        Returns:
            Optional[ChatDocument]:
            - if msg is in expected format, return None (no objections)
            - otherwise, a ChatDocument that either contains a request to
                LLM to clarify/fix the msg, or a fixed version of the LLM's original
                message.
        """
        if msg is None or isinstance(msg, str):
            return None
        recipient = msg.metadata.recipient
        has_func_call = msg.function_call is not None
        content = msg.content

        if recipient != "":
            # there is a clear recipient, return None (no objections)
            return None

        attachment: None | ChatDocAttachment = None
        responder: None | Entity = None
        sender_name = self.config.name
        if has_func_call or "TOOL" in content:
            # assume it is meant for Coder, so simply set the recipient field,
            # and the parent task loop continues as normal
            # TODO- but what if it is not a legit function call
            recipient = self.config.tool_recipient
        elif content in self.config.recipients:
            # the incoming message is a clarification response from LLM
            recipient = content
            if msg.attachment is not None and isinstance(
                msg.attachment, ValidatorAttachment
            ):
                content = msg.attachment.content
            else:
                logger.warning("ValidatorAgent: Did not find content to correct")
                content = ""
            # we've used the attachment, don't need anymore
            attachment = ValidatorAttachment(content="")
            # we are rewriting an LLM message from parent, so
            # pretend it is from LLM
            responder = Entity.LLM
            sender_name = ""
        else:
            # save the original message so when the Validator
            # receives the LLM clarification,
            # it can use it as the `content` field
            attachment = ValidatorAttachment(content=content)
            content = """
            Is this message for DockerExpert, or for Coder?
            Please simply respond with "DockerExpert" or "Coder"
            """
        return ChatDocument(
            content=content,
            function_call=msg.function_call if has_func_call else None,
            attachment=attachment,
            metadata=ChatDocMetaData(
                source=Entity.AGENT,
                sender=Entity.AGENT,
                parent_responder=responder,
                sender_name=sender_name,
                recipient=recipient,
            ),
        )