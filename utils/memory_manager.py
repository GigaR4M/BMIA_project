
import logging
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, db, chat_handler):
        self.db = db
        self.chat_handler = chat_handler
        self.model_name = "models/text-embedding-004" # Standard efficient embedding model

    async def get_relevant_context(self, guild, user, message_content: str) -> str:
        """
        Gathers all layers of context (Global, User, Long-term) and constructs the context block.
        """
        guild_id = guild.id
        user_id = user.id

        # 1. Fetch Global Context
        server_ctx = await self.db.get_server_context(guild_id)
        
        # 2. Fetch User Profile
        user_profile = await self.db.get_user_bot_profile(user_id, guild_id)
        
        # 3. Fetch Relevant Memories (Vector Search)
        relevant_memories = []
        try:
            # Generate embedding for the current query
            embedding = await self._generate_embedding(message_content)
            if embedding:
                relevant_memories = await self.db.search_memories(guild_id, embedding, user_id, limit=3)
        except Exception as e:
            logger.error(f"Error fetching memories: {e}")

        # 4. Construct the Text Block
        context_parts = []
        
        # Server Block
        context_parts.append(f"Contexto do Servidor '{guild.name}':")
        if server_ctx:
            if server_ctx.get('theme'): context_parts.append(f"- Tema: {server_ctx['theme']}")
            if server_ctx.get('rules'): context_parts.append(f"- Regras: {server_ctx['rules']}")
            if server_ctx.get('tone'): context_parts.append(f"- Tom Desejado: {server_ctx['tone']}")
            if server_ctx.get('extras'): context_parts.append(f"- Extras: {server_ctx['extras']}")
        else:
            context_parts.append("- (Nenhum contexto global definido ainda)")

        # User Block
        context_parts.append(f"\nSobre o Usuário {user.display_name}:")
        if user_profile:
             if user_profile.get('nickname_preference'): context_parts.append(f"- Prefere ser chamado de: {user_profile['nickname_preference']}")
             if user_profile.get('tone_preference'): context_parts.append(f"- Preferência de resposta: {user_profile['tone_preference']}")
             if user_profile.get('interaction_summary'): context_parts.append(f"- Histórico: {user_profile['interaction_summary']}")
        else:
             context_parts.append("- (Novo usuário ou sem perfil)")

        # Memories Block
        if relevant_memories:
            context_parts.append(f"\nMemórias Relevantes (Fatos/Decisões Passadas):")
            for mem in relevant_memories:
                similarity = f" ({mem.get('similarity', 0):.2f})" if 'similarity' in mem else ""
                context_parts.append(f"- {mem['content']}{similarity}")

        return "\n".join(context_parts)

    async def process_message_for_memory(self, guild_id: int, user_id: int, user_content: str, bot_response: str):
        """
        Background task: Analyzes the conversation turn to see if new memories or profile updates are needed.
        """
        prompt = f"""
        Analise a seguinte interação entre um usuário e o bot.
        Usuário: {user_content}
        Bot: {bot_response}

        IDENTIFIQUE se há alguma informação nova e PERMANENTE que deve ser salva em memória de longo prazo ou no perfil do usuário.
        
        Critérios:
        1. Fatos sobre o usuário (nome, gosto, profissão, jogo favorito).
        2. Preferências explicitas ("Gosto de respostas curtas").
        3. Decisões ou fatos do servidor ("O evento é sexta-feira").
        4. NÃO salve cumprimentos, piadas banais ou conversa fiada.
        5. NÃO salve informações sensíveis (senhas, documentos).

        Retorne APENAS um JSON:
        {{
            "save_memory": boolean,
            "memory_content": "texto resumido do fato",
            "is_user_profile_update": boolean,
            "profile_update": {{ "key": "value" }} (keys permitidas: nickname_preference, tone_preference)
        }}
        """

        try:
            # Reusing the existing chat handler's initialized model logic if possible, 
            # but ideally we want a separate call. Using the main 'generate_response' might be messy due to history.
            # We will use the underlying model directly if exposed, or call generic generate.
            # Assuming ChatHandler exposes the model or method.
            
            # Use `gemini-1.5-flash` or similar cheap model for this overhead task
            model = genai.GenerativeModel('gemini-1.5-flash') 
            response = await model.generate_content_async(prompt)
            data = self._parse_json_response(response.text)

            if data and data.get("save_memory"):
                content = data["memory_content"]
                
                # Check privacy
                if not content: return 

                # Generate embedding
                embedding = await self._generate_embedding(content)
                
                # Store
                is_profile = data.get("is_user_profile_update")
                if is_profile:
                    updates = data.get("profile_update", {})
                    if updates:
                        await self.db.update_user_bot_profile(user_id, guild_id, updates)
                        logger.info(f"Updated profile for user {user_id}")
                else:
                    # General memory
                    await self.db.store_memory(guild_id, content, embedding, user_id)
                    logger.info(f"Stored new memory for user {user_id}: {content}")

        except Exception as e:
            logger.error(f"Error processing memory: {e}")

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            # We use embed_content from genai
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def _parse_json_response(self, text: str) -> Dict:
        """Helper to safely parse JSON from LLM response which might contain backticks."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text)
        except:
            return {}

