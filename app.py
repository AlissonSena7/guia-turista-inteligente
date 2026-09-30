"""Aplicação Flask Principal - Guia do Turista Inteligente (API Gateway em Python)."""

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any

import httpx
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import (
    DATA_DIR,
    ESTADOS_BRASIL,
    GOOGLE_CLIENT_ID,
    PORT,
    VIAGENS_FILE,
)
from planejamento import orquestrar_roteiro
from services import (
    buscar_coordenadas,
    obter_clima,
    obter_percurso,
    verificar_token_google,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "guia-turista-secret-key-2026-python")

# Controle de concorrência para leitura e escrita segura no arquivo JSON
DATA_DIR.mkdir(parents=True, exist_ok=True)
lock_arquivo_json = threading.Lock()

# Armazenamento volátil de roteiros em memória para sessões de visitantes
viagens_visitante_memoria: dict[str, list[dict[str, Any]]] = {}

# Controle de concorrência e idempotência contra cliques duplicados
requisicoes_ativas: set[str] = set()
requisicoes_recentes: dict[str, float] = {}
lock_requisicoes = threading.Lock()

# Sessão do modo visitante (mantida apenas em memória)
USUARIO_VISITANTE = "visitante"
AVATAR_VISITANTE = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='1' height='1'/%3E"
)

# Janela (segundos) para descartar reenvio/clique duplicado da mesma viagem
JANELA_IDEMPOTENCIA_SEGUNDOS = 8.0


# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 4: Persistência JSON, Sanitização e Manipulação
# ==============================================================================


def sanitizar_entrada(texto: str, max_len: int = 80) -> str:
    """Higieniza entradas de texto removendo tags HTML, caracteres de controle e espaços extras."""
    # TODO (Aluno 4): Implementar a sanitização de texto via regex r'<[^>]*>'
    pass


def criar_estrutura_padrao_viagens() -> dict[str, Any]:
    """Retorna a estrutura inicial do payload JSON de viagens com metadados e provedores."""
    return {
        "versao_schema": "1.0",
        "descricao": "Base consolidada de roteiros turísticos e telemetria por usuário",
        "atualizado_em": datetime.now().isoformat(),
        "total_usuarios": 0,
        "total_roteiros": 0,
        "provedores": {
            "geocoding": "Open-Meteo Geocoding API",
            "previsao_tempo": "Open-Meteo Forecast API",
            "roteamento": "OSRM Routing Engine",
            "inteligencia_artificial": "Google Gemini (gemini-3.6-flash)",
        },
        "usuarios": {},
    }


def carregar_dados_viagens_json() -> dict[str, Any]:
    """Lê a base completa de viagens de static/data/viagens.json de forma thread-safe com lock_arquivo_json."""
    # TODO (Aluno 4): Implementar leitura segura do JSON com lock_arquivo_json
    pass


def salvar_dados_viagens_json(dados_completos: dict[str, Any]) -> None:
    """Persiste a base hierárquica em static/data/viagens.json com lock_arquivo_json e indentação de 2 espaços."""
    # TODO (Aluno 4): Implementar escrita segura no arquivo JSON com lock_arquivo_json
    pass


def obter_viagens_usuario(user_id: str) -> list[dict[str, Any]]:
    """Recupera a lista de roteiros: da memória para visitantes ou do arquivo JSON para logados."""
    # TODO (Aluno 4): Implementar recuperação de roteiros por usuário (memória vs JSON)
    pass


def adicionar_viagem_usuario(
    user_id: str,
    item: dict[str, Any],
    perfil_usuario: dict[str, Any] | None = None,
) -> None:
    """Adiciona um novo roteiro: na memória para visitante ou grava no JSON para usuário logado."""
    # TODO (Aluno 4): Implementar inserção de novo roteiro na estrutura de dados
    pass


def remover_viagem_usuario(user_id: str, viagem_id: str) -> None:
    """Remove um roteiro específico pelo ID."""
    # TODO (Aluno 4): Implementar remoção de roteiro pelo ID
    pass


# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 3: Backend Gateway, Sessões, Rotas & Idempotência
# ==============================================================================


def usuario_atual() -> dict[str, Any] | None:
    """Retorna o dicionário do usuário autenticado na sessão, ou None se não houver."""
    usuario = session.get("usuario")
    return usuario if isinstance(usuario, dict) else None


def descartar_requisicoes_expiradas() -> None:
    """Poda 'requisicoes_recentes' das chaves cuja janela de idempotência já passou.

    Deve ser chamado com 'lock_requisicoes' já adquirido.
    """
    agora = time.time()
    for chave in [
        chave
        for chave, marca in requisicoes_recentes.items()
        if agora - marca >= JANELA_IDEMPOTENCIA_SEGUNDOS
    ]:
        requisicoes_recentes.pop(chave, None)


@app.route("/", methods=["GET"])
def index():
    """Renderiza a página principal (SSR com Jinja2)."""
    usuario = usuario_atual()
    viagens = (
        obter_viagens_usuario(str(usuario.get("id") or USUARIO_VISITANTE)) or []
        if usuario
        else []
    )
    return render_template(
        "index.html",
        usuario=usuario,
        client_id=GOOGLE_CLIENT_ID,
        ufs=ESTADOS_BRASIL.keys(),
        viagens=viagens,
    )


@app.route("/auth/google/callback", methods=["POST"])
def google_callback():
    """Recebe a credencial JWT do Google no campo 'credential' e valida 100% no Python."""
    credencial = request.form.get("credential", "").strip()
    if not credencial:
        return redirect(url_for("index"))

    with httpx.Client(timeout=6.0) as client:
        usuario = verificar_token_google(client, credencial)

    if not isinstance(usuario, dict):
        flash("Não foi possível validar sua conta Google. Tente novamente.", "erro")
        return redirect(url_for("index"))

    session["usuario"] = usuario
    return redirect(url_for("index"))


@app.route("/auth/demo", methods=["GET"])
def login_demo():
    """Modo Visitante para desenvolvimento e testes locais."""
    session["usuario"] = {
        "id": USUARIO_VISITANTE,
        "nome": "Viajante Convidado",
        "email": "visitante@local",
        "foto": AVATAR_VISITANTE,
    }
    return redirect(url_for("index"))


@app.route("/auth/logout", methods=["GET"])
def logout():
    """Encerra a sessão e descarta a memória de visitante."""
    if (usuario_atual() or {}).get("id") == USUARIO_VISITANTE:
        viagens_visitante_memoria.pop(USUARIO_VISITANTE, None)
    session.clear()
    return redirect(url_for("index"))


@app.route("/viagens/criar", methods=["POST"])
def criar_viagem():
    """Orquestra as APIs externas sob deduplicação (locks) e persiste o roteiro gerado."""
    usuario = usuario_atual()
    if usuario is None:
        flash("Faça login para planejar roteiros.", "erro")
        return redirect(url_for("index"))

    origem_cidade = request.form.get("origem_cidade", "").strip()[:80]
    origem_uf = request.form.get("origem_uf", "").strip().upper()[:2]
    destino_cidade = request.form.get("destino_cidade", "").strip()[:80]
    destino_uf = request.form.get("destino_uf", "").strip().upper()[:2]
    if (
        not (origem_cidade and destino_cidade)
        or origem_uf not in ESTADOS_BRASIL
        or destino_uf not in ESTADOS_BRASIL
    ):
        flash("Informe cidade e UF válidas para origem e destino.", "erro")
        return redirect(url_for("index"))

    user_id = str(usuario.get("id") or USUARIO_VISITANTE)
    chave = f"{user_id}|{origem_uf}:{origem_cidade}|{destino_uf}:{destino_cidade}"

    with lock_requisicoes:
        descartar_requisicoes_expiradas()
        em_curso = chave in requisicoes_ativas
        recente = (
            time.time() - requisicoes_recentes.get(chave, 0.0)
            < JANELA_IDEMPOTENCIA_SEGUNDOS
        )
        if em_curso or recente:
            flash("Este roteiro já está sendo gerado. Aguarde alguns segundos.", "aviso")
            return redirect(url_for("index"))
        requisicoes_ativas.add(chave)

    try:
        with httpx.Client(timeout=8.0) as client:
            lat_o, lon_o, nome_o = buscar_coordenadas(client, origem_cidade, origem_uf)
            lat_d, lon_d, nome_d = buscar_coordenadas(client, destino_cidade, destino_uf)
            percurso = obter_percurso(client, lat_o, lon_o, lat_d, lon_d)
            clima = obter_clima(client, lat_d, lon_d)

        roteiro = orquestrar_roteiro(
            perfil=usuario, clima=clima, rota=percurso, destino=nome_d
        )
        adicionar_viagem_usuario(
            user_id,
            {
                "id": uuid.uuid4().hex,
                "origem": nome_o,
                "destino": nome_d,
                "percurso": percurso,
                "clima": clima,
                "dicas_destino": roteiro["itinerario"],
            },
            usuario,
        )
    except Exception:  # noqa: BLE001
        with lock_requisicoes:
            requisicoes_ativas.discard(chave)
        flash("Não foi possível gerar o roteiro agora. Tente em instantes.", "erro")
        return redirect(url_for("index"))

    # Só marca como recente após o sucesso; em erro a chave é liberada para nova tentativa
    with lock_requisicoes:
        requisicoes_ativas.discard(chave)
        requisicoes_recentes[chave] = time.time()

    return redirect(url_for("index"))


@app.route("/viagens/deletar/<string:viagem_id>", methods=["POST"])
def deletar_viagem(viagem_id: str):
    """Exclui um roteiro da lista do usuário, validando a titularidade do ID."""
    usuario = usuario_atual()
    if usuario is None:
        flash("Faça login para gerenciar roteiros.", "erro")
        return redirect(url_for("index"))

    user_id = str(usuario.get("id") or USUARIO_VISITANTE)
    ids_usuario = {
        v.get("id") for v in (obter_viagens_usuario(user_id) or []) if isinstance(v, dict)
    }
    if viagem_id not in ids_usuario:
        flash("Roteiro não encontrado na sua lista.", "erro")
        return redirect(url_for("index"))

    remover_viagem_usuario(user_id, viagem_id)
    flash("Roteiro excluído com sucesso.", "sucesso")
    return redirect(url_for("index"))


# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 4: Endpoint REST e Error Handlers Globais
# ==============================================================================


@app.route("/viagens/json", methods=["GET"])
@app.route("/api/viagens/json", methods=["GET"])
@app.route("/api/viagens", methods=["GET"])
def ver_viagens_json():
    """Retorna a base consolidada de static/data/viagens.json com suporte dinâmico a visitantes."""
    # TODO (Aluno 4): Retornar jsonify() da árvore consolidada de viagens
    pass


@app.errorhandler(405)
def metodo_nao_permitido(error):
    """Fallback para acessos GET em rotas POST (ex: digitar /viagens/criar na barra de endereços)."""
    # TODO (Aluno 4): Interceptar erro 405 e redirecionar suavemente para url_for('index')
    pass


@app.errorhandler(404)
def pagina_nao_encontrada(error):
    """Fallback para rotas inexistentes redirecionando suavemente para a página principal."""
    # TODO (Aluno 4): Interceptar erro 404 e redirecionar suavemente para url_for('index')
    pass


if __name__ == "__main__":
    print(f"🌍 Servidor Flask Guia do Turista rodando em http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
