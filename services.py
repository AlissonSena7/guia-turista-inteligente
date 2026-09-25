# Serviços de integração com APIs externas (Google OAuth, Open-Meteo e OSRM)

import re
from typing import Any

import httpx
import requests

from config import ESTADOS_BRASIL, GOOGLE_CLIENT_ID

# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 1: APIs REST, Autenticação JWT e Geocodificação
# ==============================================================================


def verificar_token_google(client: httpx.Client, token: str) -> dict[str, Any] | None:
    """Valida o token JWT no endpoint oficial 'https://oauth2.googleapis.com/tokeninfo'.

    Verifica se o token foi emitido para o GOOGLE_CLIENT_ID configurado no projeto
    e retorna o payload do usuário (sub, name, email, picture) ou None se for inválido.
    """
    # TODO (Aluno 1): Implementar a validação do token JWT junto à API do Google OAuth2
    pass


def obter_sigla_uf(admin1: str, uf_informada: str = "") -> str:
    """Converte o estado retornado pela API (admin1) para a sigla oficial de 2 letras (ex: 'PI').

    Caso a API retorne um nome completo (ex: 'Piauí'), normaliza para a sigla 'PI'.
    Caso contrário, utiliza a UF informada como fallback se for válida.
    """
    if admin1:
        admin1_normalizado = admin1.strip().lower()
        for sigla, nome_estado in ESTADOS_BRASIL.items():
            if nome_estado.lower() == admin1_normalizado:
                return sigla
        admin1_limpo = admin1.strip().upper()
        if admin1_limpo in ESTADOS_BRASIL:
            return admin1_limpo

    if uf_informada:
        uf_limpa = uf_informada.strip().upper()
        if uf_limpa in ESTADOS_BRASIL:
            return uf_limpa

    return uf_informada.strip().upper() if uf_informada else ""


def buscar_coordenadas(
    client: httpx.Client, cidade: str, uf: str = ""
) -> tuple[float, float, str]:
    """Consulta o Open-Meteo Geocoding com filtro Brasil (country_codes=BR) e timeout=4.0s.

    Retorna a tupla (latitude, longitude, nome_formatado). Caso a busca falhe,
    aplica fallback seguro retornando (0.0, 0.0, "Cidade - UF").
    """
    cidade_limpa = cidade.strip() if cidade else ""
    uf_limpa = uf.strip().upper() if uf else ""
    fallback: tuple[float, float, str] = (
        0.0,
        0.0,
        f"{cidade_limpa} - {uf_limpa}" if cidade_limpa else "Cidade - UF",
    )

    if not cidade_limpa:
        return fallback

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params: dict[str, Any] = {
        "name": cidade_limpa,
        "country": "BR",
        "language": "pt",
        "count": 5,
        "format": "json",
    }

    try:
        requisicao_cliente = client if client is not None else httpx.Client(timeout=5.0)
        resposta = requisicao_cliente.get(url, params=params, timeout=5.0)
        if client is None:
            requisicao_cliente.close()

        if resposta.status_code != 200:
            return fallback

        dados = resposta.json()
        resultados = dados.get("results", [])
        if not resultados or not isinstance(resultados, list):
            return fallback

        candidato_brasil: dict[str, Any] | None = None
        for r in resultados:
            if not isinstance(r, dict):
                continue
            pais_code = str(r.get("country_code", "")).upper()
            admin1_api = str(r.get("admin1", ""))
            sigla_detectada = obter_sigla_uf(admin1_api, uf_limpa)

            if pais_code != "BR":
                continue

            if uf_limpa and sigla_detectada == uf_limpa:
                candidato_brasil = r
                break

            if candidato_brasil is None:
                candidato_brasil = r

        if candidato_brasil is None:
            return fallback

        lat = float(candidato_brasil.get("latitude", 0.0))
        lon = float(candidato_brasil.get("longitude", 0.0))
        nome_cidade = str(candidato_brasil.get("name", cidade_limpa))
        admin1_retornado = str(candidato_brasil.get("admin1", ""))
        sigla_final = obter_sigla_uf(admin1_retornado, uf_limpa) or uf_limpa

        nome_formatado = (
            f"{nome_cidade} - {sigla_final}" if sigla_final else nome_cidade
        )

        return (lat, lon, nome_formatado)

    except (httpx.HTTPError, httpx.TimeoutException, ValueError, TypeError, KeyError):
        return fallback


# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 2: Telemetria Climática e Roteamento Rodoviário
# ==============================================================================


def obter_clima(client: httpx.Client, lat: float, lon: float) -> dict[str, str]:
    """Consulta o Open-Meteo Forecast e retorna temperatura (°C), umidade (%) e vento (km/h).

    Caso coordenadas sejam inválidas (0.0, 0.0) ou ocorra timeout (4.0s),
    retorna dicionário de contingência com valores 'N/D'.
    """
    fallback: dict[str, str] = {
        "temperatura": "N/D",
        "umidade": "N/D",
        "vento": "N/D",
        "condicao": "N/D",
        "chuva": "N/D",
    }

    if lat == 0.0 and lon == 0.0:
        return fallback

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "precipitation_probability",
        "timezone": "auto",
    }

    wmo_descricoes = {
        0: "Céu limpo",
        1: "Principalmente limpo",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Nevoeiro",
        48: "Nevoeiro com geada",
        51: "Garoa leve",
        53: "Garoa moderada",
        55: "Garoa densa",
        61: "Chuva fraca",
        63: "Chuva moderada",
        65: "Chuva forte",
        71: "Neve fraca",
        73: "Neve moderada",
        75: "Neve forte",
        80: "Pancadas de chuva leves",
        81: "Pancadas de chuva moderadas",
        82: "Pancadas de chuva violentas",
        95: "Tempestade",
        96: "Tempestade com granizo leve",
        99: "Tempestade com granizo forte",
    }

    try:
        if client is not None:
            resposta = client.get(url, params=params, timeout=4.0)
        else:
            with httpx.Client(timeout=4.0) as default_client:
                resposta = default_client.get(url, params=params)

        if resposta.status_code != 200:
            return fallback

        dados = resposta.json()
        current = dados.get("current", {})
        temp = current.get("temperature_2m")
        umid = current.get("relative_humidity_2m")
        vento = current.get("wind_speed_10m")
        weather_code = current.get("weather_code")

        condicao = wmo_descricoes.get(weather_code, "Tempo estável") if weather_code is not None else "N/D"

        hourly_prob = dados.get("hourly", {}).get("precipitation_probability", [])
        prob_chuva = f"{hourly_prob[0]}%" if hourly_prob and hourly_prob[0] is not None else "0%"

        return {
            "temperatura": f"{temp}°C" if temp is not None else "N/D",
            "umidade": f"{umid}%" if umid is not None else "N/D",
            "vento": f"{vento} km/h" if vento is not None else "N/D",
            "condicao": condicao,
            "chuva": prob_chuva,
        }
    except (requests.RequestException, httpx.HTTPError, KeyError, ValueError, TypeError):
        return fallback


def obter_percurso(
    client: httpx.Client, lat_o: float, lon_o: float, lat_d: float, lon_d: float
) -> dict[str, str]:
    """Consulta o OSRM e calcula distância em km e duração de viagem de carro.

    Em caso de trajetos sem estradas (ex: ilhas) ou timeout (6.0s),
    retorna dicionário com fallback descritivo ('Sem rota direta' / 'Considere voos ou barcos').
    """
    fallback: dict[str, str] = {
        "distancia": "Sem rota direta",
        "tempo": "Considere voos ou barcos",
        "duracao": "Considere voos ou barcos",
    }

    if (lat_o == 0.0 and lon_o == 0.0) or (lat_d == 0.0 and lon_d == 0.0):
        return fallback

    url = f"https://router.project-osrm.org/route/v1/driving/{lon_o},{lat_o};{lon_d},{lat_d}"

    try:
        if client is not None:
            resposta = client.get(url, params={"overview": "false"}, timeout=6.0)
        else:
            with httpx.Client(timeout=6.0) as default_client:
                resposta = default_client.get(url, params={"overview": "false"})

        if resposta.status_code != 200:
            return fallback

        dados = resposta.json()
        if dados.get("code") != "Ok" or not dados.get("routes"):
            return fallback

        rota_principal = dados["routes"][0]
        distancia_metros = float(rota_principal.get("distance", 0.0))
        duracao_segundos = float(rota_principal.get("duration", 0.0))

        dist_km = distancia_metros / 1000.0
        dur_min = round(duracao_segundos / 60.0)

        distancia_str = f"{dist_km:.1f} km" if dist_km >= 1 else f"{dist_km:.2f} km"

        if dur_min >= 60:
            horas = dur_min // 60
            minutos = dur_min % 60
            tempo_str = f"{horas}h {minutos}min" if minutos > 0 else f"{horas}h"
        else:
            tempo_str = f"{dur_min} min"

        return {
            "distancia": distancia_str,
            "tempo": tempo_str,
            "duracao": f"{dur_min} min",
        }
    except (requests.RequestException, httpx.HTTPError, KeyError, ValueError, TypeError):
        return fallback
