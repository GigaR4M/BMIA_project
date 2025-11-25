# setup_roles.py - Script para configurar cargos automáticos baseados em patentes

"""
Script auxiliar para configurar os cargos automáticos de patentes no servidor BMIA.

Patentes configuradas:
- Recruta: 0-7 dias
- Soldado: 7-28 dias
- Sargento: 28-91 dias
- Tenente: 91-182 dias
- Capitão: 182-365 dias
- Major: 365-730 dias
- Coronel: 730-1095 dias
- General: 1095+ dias

IMPORTANTE: Execute este script APÓS criar os cargos manualmente no Discord!
"""

import asyncio
from database import Database
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Configuração das patentes (nome do cargo: dias necessários)
PATENTES = {
    "Recruta": 0,
    "Soldado": 7,
    "Sargento": 28,
    "Tenente": 91,
    "Capitão": 182,
    "Major": 365,
    "Coronel": 730,
    "General": 1095
}

async def setup_auto_roles(guild_id: int, role_mappings: dict):
    """
    Configura cargos automáticos no banco de dados.
    
    Args:
        guild_id: ID do servidor Discord
        role_mappings: Dicionário {role_id: dias_necessários}
    """
    db = Database(DATABASE_URL)
    await db.connect()
    
    try:
        for role_id, days in role_mappings.items():
            await db.add_auto_role(guild_id, role_id, days)
            print(f"✅ Cargo {role_id} configurado para {days} dias")
        
        print(f"\n✅ {len(role_mappings)} cargos configurados com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao configurar cargos: {e}")
    
    finally:
        await db.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("CONFIGURAÇÃO DE CARGOS AUTOMÁTICOS - BMIA")
    print("=" * 60)
    print("\nPatentes que serão configuradas:")
    for nome, dias in PATENTES.items():
        print(f"  • {nome}: {dias} dias")
    
    print("\n" + "=" * 60)
    print("INSTRUÇÕES:")
    print("=" * 60)
    print("1. Crie os cargos manualmente no Discord primeiro")
    print("2. Copie o ID de cada cargo (Modo Desenvolvedor > Botão direito > Copiar ID)")
    print("3. Insira os IDs quando solicitado")
    print("4. O script configurará automaticamente no banco de dados")
    print("=" * 60 + "\n")
    
    guild_id = input("Digite o ID do servidor Discord: ").strip()
    
    if not guild_id.isdigit():
        print("❌ ID de servidor inválido!")
        exit(1)
    
    guild_id = int(guild_id)
    role_mappings = {}
    
    print("\nAgora, insira o ID de cada cargo:")
    print("(Deixe em branco para pular um cargo)\n")
    
    for nome, dias in PATENTES.items():
        role_id = input(f"{nome} ({dias} dias) - ID do cargo: ").strip()
        
        if role_id:
            if not role_id.isdigit():
                print(f"  ⚠️  ID inválido, pulando {nome}")
                continue
            
            role_mappings[int(role_id)] = dias
            print(f"  ✅ {nome} adicionado")
    
    if not role_mappings:
        print("\n❌ Nenhum cargo foi configurado!")
        exit(1)
    
    print(f"\n📋 Total de cargos a configurar: {len(role_mappings)}")
    confirm = input("Confirmar configuração? (s/n): ").strip().lower()
    
    if confirm == 's':
        asyncio.run(setup_auto_roles(guild_id, role_mappings))
    else:
        print("❌ Configuração cancelada")
