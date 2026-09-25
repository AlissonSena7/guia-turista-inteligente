# Módulo de Inteligência Artificial Gemini & Fallback (Guia Turístico e Culinária)

import concurrent.futures
import re
from typing import Any

from google import genai

from config import GEMINI_KEY

# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 2: Inteligência Artificial (Gemini AI) & Fallback
# ==============================================================================


def limpar_formato_texto(texto: str) -> str:
    """Remove marcações residuais de markdown (** ou *), hashtags, crases e saudações, mantendo apenas emojis."""
    if not texto:
        return ""
    # Remove blocos de código e crases
    t = re.sub(r"```[a-zA-Z]*\n?", "", texto)
    t = t.replace("`", "")
    # Remove títulos markdown
    t = re.sub(r"(?m)^#{1,6}\s*", "", t)
    # Remove marcações de negrito e itálico
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = t.replace("**", "").replace("*", "")
    # Normaliza marcadores de tópicos
    t = re.sub(r"(?m)^[-*•]\s*", "• ", t)
    # Remove saudações residuais e introduções conversacionais
    t = re.sub(
        r"^(?:Olá(?:,?\s*viajante!?)?|Bem-vindo(?:a)?!|Com certeza!|Claro!?|Aqui está o seu roteiro:?)\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    return t.strip()


def gerar_fallback_itinerario(
    destino: str,
    clima: dict[str, Any] | None = None,
    percurso: dict[str, Any] | None = None,
    perfil: dict[str, Any] | None = None,
) -> str:
    """Gera um roteiro de contingência estruturado em texto puro com emojis."""
    nome = perfil.get("nome", "Viajante") if perfil else "Viajante"
    clima_info = ""
    if clima and clima.get("temperatura") not in ("N/D", None):
        clima_info = f" Clima previsto de {clima.get('temperatura')} com {clima.get('condicao', 'tempo estável')}."

    rota_info = ""
    if percurso and percurso.get("distancia") not in ("Sem rota direta", None, "N/D"):
        tempo = percurso.get("tempo", percurso.get("duracao", ""))
        rota_info = f" Percurso estimado de {percurso.get('distancia')}" + (f" ({tempo})" if tempo else "") + "."

    return (
        f"🏛️ Guia Turístico & Culinária de {destino}\n\n"
        f"👋 Olá, {nome}! Aqui estão recomendações selecionadas para sua viagem:\n\n"
        f"📍 Principais Pontos Turísticos:\n"
        f"• Centro Histórico, monumentos culturais e marcos arquitetônicos de {destino}\n"
        f"• Parques municipais, mirantes e áreas verdes ideais para fotos\n"
        f"• Mercados públicos e feiras de artesanato tradicional\n\n"
        f"🍲 Gastronomia & Sabores Típicos:\n"
        f"• Pratos emblemáticos da culinária local e temperos regionais\n"
        f"• Restaurantes recomendados da cozinha autêntica\n"
        f"• Sobremesas caseiras, cafeterias e quiosques tradicionais\n\n"
        f"💡 Dicas de Viagem & Telemetria:\n"
        f"•{clima_info or ' Consulte a previsão meteorológica no dia dos passeios.'}\n"
        f"•{rota_info or ' Planeje paradas ao longo da estrada para viajar com tranquilidade.'}\n"
        f"• Aproveite ao máximo sua estadia em {destino} com segurança e boa viagem!"
    )


def chamar_gemini(prompt: str, modelo: str = "gemini-2.5-flash") -> str:
    """Invoca o modelo do Google Gemini utilizando GEMINI_KEY com tratamento de exceções e fallback amigável."""
    if not GEMINI_KEY or not GEMINI_KEY.strip():
        raise ValueError("Chave GEMINI_KEY não configurada no ambiente.")

    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(
            model=modelo,
            contents=prompt,
        )
        if response and hasattr(response, "text") and response.text:
            return response.text
        return ""
    except Exception as e:
        raise RuntimeError(f"Falha na comunicação com a API do Gemini: {e}") from e


def montar_prompt_telemetria(
    destino: str,
    perfil: dict[str, Any] | None = None,
    clima: dict[str, Any] | None = None,
    rota: dict[str, Any] | None = None,
) -> str:
    """Monta um prompt detalhado e grounded nos dados de telemetria meteorológica e rodoviária."""
    temp = clima.get("temperatura", "N/D") if clima else "N/D"
    cond = clima.get("condicao", "N/D") if clima else "N/D"
    chuva = clima.get("chuva", "N/D") if clima else "N/D"
    dist = rota.get("distancia", "N/D") if rota else "N/D"
    tempo = rota.get("tempo", rota.get("duracao", "N/D")) if rota else "N/D"
    nome = perfil.get("nome", "Viajante") if perfil else "Viajante"

    return f"""Você é um guia turístico e gastronômico para o destino {destino}, Brasil.
Gere um roteiro prático e personalizado para o usuário {nome}, estritamente fundamentado nestes dados de telemetria:

[DADOS DE TELEMETRIA]
- Destino: {destino}
- Clima Atual: Temperatura {temp}, Condição: {cond}, Probabilidade de chuva: {chuva}
- Percurso Rodoviário: Distância {dist}, Duração estimada: {tempo}

[DIRETRIZES DE RESPOSTA]
1. Adapte as sugestões ao clima: se houver chuva ou mau tempo, sugira museus, centros culturais e atrações cobertas. Se estiver ensolarado, sugira passeios ao ar livre, mirantes e parques.
2. Sugira os 3 principais pontos turísticos do destino e 3 pratos típicos da culinária regional.
3. Responda em texto puro com emojis descritivos. NÃO use markdown de negrito com asteriscos (**), hashtags (#) ou blocos de código. Seja direto e elegante.
"""


def obter_guia_destino_com_diagnostico(
    destino: str,
    clima: dict[str, Any] | None = None,
    percurso: dict[str, Any] | None = None,
    perfil: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Invoca o modelo 'gemini-2.5-flash' com timeout de 6.0s em ThreadPoolExecutor.

    Em caso de timeout, chave inválida ou ausência de cota, aciona automaticamente
    o gerador de contingência com roteiro estruturado em texto puro com emojis.
    Retorna a tupla (texto_guia, diagnostico_metadados).
    """
    prompt = montar_prompt_telemetria(destino=destino, perfil=perfil, clima=clima, rota=percurso)

    diagnostico: dict[str, Any] = {
        "status": "sucesso",
        "modelo": "gemini-2.5-flash",
        "provedor": "Google Gemini AI",
    }

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chamar_gemini, prompt, "gemini-2.5-flash")
            resultado_bruto = future.result(timeout=6.0)

        if not resultado_bruto or not resultado_bruto.strip():
            raise ValueError("Resposta vazia da API do Gemini.")

        texto_limpo = limpar_formato_texto(resultado_bruto)
        return texto_limpo, diagnostico
    except Exception as e:  # noqa: BLE001
        diagnostico["status"] = "fallback"
        diagnostico["modelo"] = "contingencia"
        diagnostico["motivo"] = str(e)
        texto_fallback = gerar_fallback_itinerario(
            destino=destino,
            clima=clima,
            percurso=percurso,
            perfil=perfil,
        )
        return texto_fallback, diagnostico


def orquestrar_roteiro(
    perfil: dict[str, Any] | None = None,
    clima: dict[str, Any] | None = None,
    rota: dict[str, Any] | None = None,
    destino: str = "",
) -> dict[str, Any]:
    """Orquestra a geração de roteiro recebendo perfil, clima e rota, retornando resumo e itinerário."""
    dest = destino or (perfil.get("destino", "Destino Turístico") if perfil else "Destino Turístico")
    itinerario, diagnostico = obter_guia_destino_com_diagnostico(
        destino=dest,
        clima=clima,
        percurso=rota,
        perfil=perfil,
    )
    return {
        "destino": dest,
        "itinerario": itinerario,
        "resumo_estruturado": {
            "perfil": perfil or {},
            "clima": clima or {},
            "rota": rota or {},
            "diagnostico": diagnostico,
        },
    }


def obter_guia_destino(destino: str) -> str:
    """Wrapper utilitário que retorna apenas o texto do guia."""
    texto, _ = obter_guia_destino_com_diagnostico(destino)
    return texto
