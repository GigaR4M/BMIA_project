import os
import random
import asyncio
import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

logger = logging.getLogger(__name__)

TIMEOUT_FALLBACK_MESSAGES = [
    "Deu 999ms de ping no meu neurônio artificial e fui de Vasco tentando processar isso aí 💀🔌 Manda de novo que o servidor destravou!",
    "Meu processador deu aquela congelada nível PC da Xuxa rodando Cyberpunk no ultra 🤯🔥 Manda de novo aí que deu lag mental!",
    "Caiu o FPS do meu cérebro pra 2 e tomei disconnect no meio do raciocínio 📉🤖 Repete aí na moral!",
]

QUOTA_FALLBACK_MESSAGES = [
    "Calma aí rapaziada, tão me spammando mais que call em final de campeonato! Minha placa de vídeo tá fritando 🥵🔥 Espera uns segundinhos e manda de novo!",
    "Tô em cooldown, tropa! Muita gente me marcando ao mesmo tempo, até robô precisa puxar um ar 😮‍💨⚡ Tenta de novo já já!",
]

ERROR_FALLBACK_MESSAGES = [
    "Deu tela azul nos meus circuitos tentando ler isso aí 🟦💀 Buguei mais que jogo em lançamento, manda de novo!",
    "Tropecei nos cabos do servidor e crashei o raciocínio 🤖💥 Manda de novo aí!",
]

EMPTY_FALLBACK_MESSAGES = [
    "Fiquei tão sem palavras que meu chip de áudio até mutou 😶🤖 Manda de novo aí!",
]


class ChatHandler:
    def __init__(self, api_key, model_name="gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.model = None
        self._setup()

    def _setup(self):
        if not self.api_key:
            logger.warning("ChatHandler: No API key provided. Chat features will be disabled.")
            return

        try:
            pass
        except Exception as e:
            logger.error(f"Error configuring ChatHandler: {e}")

        self.model = genai.GenerativeModel(self.model_name)

    @staticmethod
    def _extract_text_parts(response) -> str:
        """Extrai com segurança todos os blocos de texto de um response do Gemini sem disparar ValueError."""
        if not response:
            return ""
        try:
            if getattr(response, "candidates", None):
                candidate = response.candidates[0]
                if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                    text_parts = [
                        p.text
                        for p in candidate.content.parts
                        if isinstance(getattr(p, "text", None), str) and p.text.strip()
                    ]
                    if text_parts:
                        return "".join(text_parts).strip()
        except Exception:
            pass

        try:
            if isinstance(getattr(response, "text", None), str) and response.text.strip():
                return response.text.strip()
        except Exception:
            pass
        return ""

    async def generate_response(self, prompt, history=[], system_instruction=None, toolkit=None):
        """
        Generates a response given the current prompt, message history, system instruction, and optional toolkit.
        history: list of dicts with 'role' ('user' or 'model') and 'parts' (list of strings).
        system_instruction: Optional string to define the bot's persona/behavior for this turn.
        toolkit: Optional AIToolkit instance providing tools for function calling.
        """
        collected_texts = []
        executed_tool_results = []
        try:
            tools = toolkit.get_tool_callables() if toolkit else None

            model_kwargs = {}
            if system_instruction:
                model_kwargs["system_instruction"] = system_instruction
            if tools:
                model_kwargs["tools"] = tools

            model = genai.GenerativeModel(self.model_name, **model_kwargs)
            chat = model.start_chat(history=history, enable_automatic_function_calling=False)
            response = await asyncio.wait_for(chat.send_message_async(prompt), timeout=25.0)

            initial_text = self._extract_text_parts(response)
            if initial_text:
                collected_texts.append(initial_text)

            # Loop para resolver chamadas de ferramentas (Function Calling)
            max_turns = 3
            turns = 0
            while turns < max_turns:
                function_calls = []
                if getattr(response, "candidates", None) and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        fn_call = getattr(part, "function_call", None)
                        if fn_call and getattr(fn_call, "name", None):
                            function_calls.append(fn_call)

                if not function_calls:
                    break

                turns += 1
                response_parts = []
                for fn_call in function_calls:
                    fn_name = fn_call.name
                    fn_args = dict(fn_call.args) if fn_call.args else {}
                    logger.info(f"Agent BMIA executando tool '{fn_name}' com argumentos: {fn_args}")

                    fn = getattr(toolkit, fn_name, None) if toolkit else None
                    if fn:
                        try:
                            result = await fn(**fn_args)
                        except Exception as fn_err:
                            logger.error(f"Erro ao executar tool {fn_name}: {fn_err}")
                            result = {"erro": f"Erro ao executar ferramenta {fn_name}: {fn_err}"}
                    else:
                        result = {"erro": f"Ferramenta '{fn_name}' não encontrada."}

                    if fn_name != "buscar_gif":
                        executed_tool_results.append((fn_name, result))

                    response_parts.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fn_name,
                                response={"result": result}
                            )
                        )
                    )

                # Se a única tool chamada neste turno foi 'buscar_gif' e o modelo já gerou o texto da resposta,
                # encerramos o loop sem enviar um novo turno ao Gemini (evita espera extra e finish_reason=1 vazio).
                only_gif_tool = all(fc.name == "buscar_gif" for fc in function_calls)
                if only_gif_tool and collected_texts:
                    break

                response = await asyncio.wait_for(
                    chat.send_message_async(genai.protos.Content(parts=response_parts)),
                    timeout=25.0,
                )
                turn_text = self._extract_text_parts(response)
                if turn_text:
                    collected_texts.append(turn_text)

            if collected_texts:
                return "\n".join(collected_texts).strip()

            final_text = self._extract_text_parts(response)
            if final_text:
                return final_text

            # Se não veio texto mas um GIF foi selecionado pela tool buscar_gif, retorna vazio para enviar apenas o GIF
            if toolkit and getattr(toolkit, "last_gif_url", None):
                return ""

            return random.choice(EMPTY_FALLBACK_MESSAGES)

        except asyncio.TimeoutError:
            logger.warning("ChatHandler: Timeout aguardando resposta do Gemini.")
            if collected_texts:
                return "\n".join(collected_texts).strip()
            # Se alguma ferramenta de dados já foi executada antes do timeout, tenta síntese rápida sem tools
            if executed_tool_results:
                try:
                    fallback_kwargs = {"system_instruction": system_instruction} if system_instruction else {}
                    fallback_model = genai.GenerativeModel(self.model_name, **fallback_kwargs)
                    tools_summary = "\n".join(f"- {name}: {res}" for name, res in executed_tool_results)
                    synth_prompt = (
                        f"{prompt}\n\n"
                        f"[Dados já coletados do banco de dados pelas ferramentas:\n{tools_summary}]\n"
                        f"Responda diretamente ao usuário de forma descontraída e zoeira usando os dados acima:"
                    )
                    synth_resp = await asyncio.wait_for(
                        fallback_model.generate_content_async(synth_prompt),
                        timeout=15.0,
                    )
                    synth_text = self._extract_text_parts(synth_resp)
                    if synth_text:
                        return synth_text
                except Exception as synth_err:
                    logger.debug("Fallback de síntese pós-timeout falhou: %s", synth_err)
            return random.choice(TIMEOUT_FALLBACK_MESSAGES)
        except ResourceExhausted:
            logger.warning("ChatHandler: Quota exceeded.")
            if collected_texts:
                return "\n".join(collected_texts).strip()
            return random.choice(QUOTA_FALLBACK_MESSAGES)
        except Exception as e:
            logger.error(f"ChatHandler Error: {e}")
            if collected_texts:
                return "\n".join(collected_texts).strip()
            return random.choice(ERROR_FALLBACK_MESSAGES)

    def format_history(self, discord_messages, bot_user):
        """
        Converts Discord message history to Gemini chat history format,
        identifying the author and message ID of each message to prevent multi-user confusion and enable accurate tool usage.
        discord_messages: list of discord.Message objects
        bot_user: discord.User object (the bot itself)
        """
        formatted_history = []
        for msg in discord_messages:
            if not msg.content:
                continue

            if msg.author == bot_user:
                role = "model"
                content = msg.content
            else:
                role = "user"
                author_name = getattr(msg.author, "display_name", str(msg.author))
                author_id = getattr(msg.author, "id", "Desconhecido")
                msg_id = getattr(msg, "id", "Desconhecido")
                content = f"[Mensagem ID: {msg_id} | Autor: {author_name} | ID_Usuario: {author_id}]: {msg.content}"

            formatted_history.append({
                "role": role,
                "parts": [content]
            })
        return formatted_history
