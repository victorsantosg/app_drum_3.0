import sqlite3
import json
import logging

DB_FILE = "grooves.db"

# Configuração do logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app_debug.log", encoding="utf-8"),  # salva em arquivo
        logging.StreamHandler()  # também mostra no console
    ]
)

def init_db():
    logging.debug("Inicializando banco de dados...")
    """Cria a tabela de grooves se não existir."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS grooves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bpm INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logging.info("Banco de dados inicializado com sucesso.")

def save_groove(name, bpm, sequence, timbres):
    logging.debug(f"Salvando groove: name={name}, bpm={bpm}")
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        data = {"sequence": sequence, "timbres": timbres}
        logging.debug(f"Dados JSON -> {data}")
        c.execute("INSERT INTO grooves (name, bpm, data) VALUES (?,?,?)",
                  (name, bpm, json.dumps(data)))
        groove_id = c.lastrowid  # captura o ID do groove inserido
        conn.commit()
        conn.close()
        logging.info(f"Groove salvo com sucesso! ID={groove_id}")
        return groove_id   # retorna para o DrumMachine
    except Exception as e:
        print("Erro ao salvar groove:", e)
        logging.error("Erro ao salvar groove!", exc_info=True)
        return None


def load_all_grooves():
    logging.debug("Carregando lista de grooves do banco...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, bpm FROM grooves")
    rows = c.fetchall()
    conn.close()
    logging.info(f"Total de grooves carregados: {len(rows)}")
    return rows

def load_groove_by_id(groove_id):
    logging.debug(f"Carregando groove ID={groove_id}")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT data, bpm FROM grooves WHERE id = ?", (groove_id,))
    row = c.fetchone()
    conn.close()
    if row:
        logging.info(f"Groove ID={groove_id} carregado com sucesso")
        return json.loads(row[0]), row[1]
    logging.warning(f"Groove ID={groove_id} não encontrado")
    return None, None

def delete_groove(groove_id):
    logging.debug(f"Deletando groove ID={groove_id}")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM grooves WHERE id = ?", (groove_id,))
    conn.commit()
    conn.close()
    logging.info(f"Groove ID={groove_id} deletado com sucesso.")
