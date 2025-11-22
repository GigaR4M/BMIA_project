# 🚀 Guia de Deploy no ShardCloud

## ✅ Status do Projeto
- ✅ Código commitado na branch `feature/novas-funcionalidades`
- ✅ Push realizado para GitHub
- ✅ Pronto para deploy!

## 📋 Checklist Pré-Deploy

### 1. Configurar Supabase (OBRIGATÓRIO para estatísticas)
1. Acesse [supabase.com](https://supabase.com)
2. Crie novo projeto
   - Nome: `BMIA Stats` (ou qualquer nome)
   - Região: **South America (São Paulo)** ⭐
   - Senha do banco: **Anote em local seguro!**
3. Aguarde criação do projeto (~2 minutos)
4. Vá em **Project Settings** → **Database**
5. Copie a **Connection String (URI)**
   - Formato: `postgresql://postgres.[ref]:[senha]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres`

### 2. Preparar Variáveis de Ambiente

Você precisará configurar estas variáveis no ShardCloud:

```
DISCORD_TOKEN=seu_token_do_discord
GEMINI_API_KEY=sua_chave_gemini
DATABASE_URL=postgresql://postgres.[ref]:[senha]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
PORT=10000
```

## 🌐 Deploy no ShardCloud

### Passo 1: Criar Novo Deployment
1. Acesse [shardcloud.app](https://shardcloud.app)
2. Vá em **Deployments** → **New Deployment**
3. Selecione **GitHub Repository**

### Passo 2: Conectar Repositório
1. Autorize acesso ao GitHub (se necessário)
2. Selecione o repositório: `GigaR4M/BMIA_project`
3. Selecione a branch: `feature/novas-funcionalidades`

### Passo 3: Configurar Build
```
Build Command: pip install -r requirements.txt
Start Command: python main.py
```

### Passo 4: Adicionar Variáveis de Ambiente
No painel do ShardCloud, adicione as variáveis:

| Variável | Valor |
|----------|-------|
| `DISCORD_TOKEN` | Cole seu token do Discord |
| `GEMINI_API_KEY` | Cole sua chave do Gemini |
| `DATABASE_URL` | Cole a connection string do Supabase |
| `PORT` | `10000` |

### Passo 5: Deploy!
1. Clique em **Deploy**
2. Aguarde o build (~2-3 minutos)
3. Verifique os logs para confirmar:
   - ✅ Bot conectado ao Discord
   - ✅ Banco de dados conectado
   - ✅ Comandos slash sincronizados

## 🔍 Verificação Pós-Deploy

### 1. Verificar Logs
Procure por estas mensagens:
```
🤖 Bot conectado como BMIA#1234!
🛡️  Moderação: Análise em lotes a cada 15 segundos
✅ Conectado ao banco de dados PostgreSQL
✅ Schema do banco de dados inicializado
📊 Sistema de estatísticas ativado!
✅ Bot totalmente inicializado!
```

### 2. Testar no Discord
```
1. Envie algumas mensagens no servidor
2. Digite: /stats
3. Você deve ver os comandos disponíveis:
   - /stats server
   - /stats me
   - /stats top
   - /stats channels
4. Execute: /stats server
5. Deve mostrar estatísticas (mesmo que zeradas inicialmente)
```

### 3. Verificar Banco de Dados
1. Acesse o Supabase Dashboard
2. Vá em **Table Editor**
3. Você deve ver as tabelas criadas:
   - `users`
   - `channels`
   - `messages`
   - `voice_activity`
   - `daily_stats`

## ⚠️ Troubleshooting

### Erro: "DATABASE_URL não configurada"
- ✅ Verifique se adicionou a variável no ShardCloud
- ✅ Confirme que o formato está correto
- ✅ Reinicie o deployment

### Erro: "Comandos slash não aparecem"
- ✅ Aguarde até 1 hora (Discord pode demorar)
- ✅ Verifique se o bot tem permissão `applications.commands`
- ✅ Reinvite o bot com o link correto

### Erro: "Connection refused" (Banco)
- ✅ Verifique se o projeto Supabase está ativo
- ✅ Confirme a connection string
- ✅ Verifique se a senha está correta

### Bot funciona mas sem estatísticas
- ✅ Isso é normal! O bot funciona em modo híbrido
- ✅ Moderação funciona independentemente
- ✅ Estatísticas só ativam com DATABASE_URL configurada

## 📊 Monitoramento

### Logs do ShardCloud
Monitore para:
- Erros de conexão
- Mensagens moderadas
- Estatísticas coletadas

### Supabase Dashboard
Verifique:
- Número de registros crescendo
- Uso de storage
- Queries executadas

## 🎉 Pronto!

Seu bot agora está rodando com:
- ✅ Moderação automática com IA
- ✅ Sistema completo de estatísticas
- ✅ Comandos slash modernos
- ✅ Rastreamento de voz
- ✅ Banco de dados PostgreSQL

## 📝 Próximos Passos (Opcional)

1. **Merge para Master**
   ```bash
   git checkout master
   git merge feature/novas-funcionalidades
   git push origin master
   ```

2. **Atualizar Deploy**
   - No ShardCloud, mude a branch para `master`
   - Redeploy automático

3. **Monitorar Uso**
   - Acompanhe limites do Supabase free tier
   - 500MB de dados
   - 50K usuários ativos/mês

## 🆘 Suporte

Problemas? Verifique:
1. Logs do ShardCloud
2. Logs do Supabase
3. Permissões do bot no Discord
4. Variáveis de ambiente configuradas

---

**Boa sorte com o deploy! 🚀**
