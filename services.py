# Serviços de integração com APIs externas (Google OAuth, Open-Meteo e OSRM)

import math
from typing import Any

import httpx
import requests

from config import ESTADOS_BRASIL, GOOGLE_CLIENT_ID, OSRM_BASE_URL

# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 1: APIs REST, Autenticação JWT e Geocodificação
# ==============================================================================


def verificar_token_google(client: httpx.Client, token: str) -> dict[str, Any] | None:
    """Valida o token JWT no endpoint oficial 'https://oauth2.googleapis.com/tokeninfo'.

    Verifica se o token foi emitido para o GOOGLE_CLIENT_ID configurado no projeto
    e retorna o payload do usuário (sub, name, email, picture) ou None se for inválido.
    """
    if not token or not isinstance(token, str):
        return None

    token_limpo = token.strip()
    if not token_limpo:
        return None

    url = "https://oauth2.googleapis.com/tokeninfo"
    params: dict[str, Any] = {"id_token": token_limpo}

    try:
        requisicao_cliente = client if client is not None else httpx.Client(timeout=6.0)
        resposta = requisicao_cliente.get(url, params=params, timeout=6.0)
        if client is None:
            requisicao_cliente.close()

        if resposta.status_code != 200:
            return None

        payload = resposta.json()
        if not isinstance(payload, dict):
            return None

        error_desc = payload.get("error_description") or payload.get("error")
        if error_desc:
            return None

        aud_client = str(payload.get("aud", "")).strip()
        if not aud_client:
            return None

        client_ids_validos = {str(GOOGLE_CLIENT_ID).strip()}
        if aud_client not in client_ids_validos:
            issuer_azp = str(payload.get("azp", "")).strip()
            if issuer_azp not in client_ids_validos:
                return None

        sub_usuario = str(payload.get("sub", "")).strip()
        if not sub_usuario:
            return None

        email_usuario = str(payload.get("email", "")).strip()
        email_verificado = str(payload.get("email_verified", "")).lower() == "true"
        nome_usuario = str(payload.get("name", "")).strip() or email_usuario.split("@")[0]
        foto_usuario = str(payload.get("picture", "")).strip()
        expiracao_token = str(payload.get("exp", "")).strip()

        return {
            "sub": sub_usuario,
            "id": sub_usuario,
            "email": email_usuario,
            "email_verificado": email_verificado,
            "nome": nome_usuario,
            "name": nome_usuario,
            "foto": foto_usuario,
            "picture": foto_usuario,
            "aud": aud_client,
            "exp": expiracao_token,
            "autenticado": True,
        }

    except (httpx.HTTPError, httpx.TimeoutException, ValueError, TypeError, KeyError):
        return None


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


def _coordenada_normalizada(lat: Any, lon: Any) -> tuple[float, float] | None:
    """Valida e normaliza um par (lat, lon) para o formato float exigido pelo OSRM.

    Retorna None quando a coordenada é ausente, não numérica, está fora da faixa
    geodésica (lat -90..90 / lon -180..180) ou é o sentinela (0.0, 0.0) devolvido
    pelo fallback de geocodificação.
    """
    try:
        lat_num = float(lat)
        lon_num = float(lon)
    except (TypeError, ValueError):
        return None

    if math.isnan(lat_num) or math.isnan(lon_num):
        return None
    if not -90.0 <= lat_num <= 90.0 or not -180.0 <= lon_num <= 180.0:
        return None
    if lat_num == 0.0 and lon_num == 0.0:
        return None

    return lat_num, lon_num


def _medida_positiva(valor: Any) -> float | None:
    """Converte um campo numérico do OSRM em float, exigindo que seja maior que zero.

    Retorna None para valores ausentes, não numéricos, booleanos, NaN ou <= 0,
    evitando que a aplicação exiba distância/duração inventadas.
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    if math.isnan(numero) or numero <= 0.0:
        return None
    return numero


def formatar_duracao(duracao_segundos: float) -> str:
    """Converte a duração em segundos do OSRM para o formato legível 'Xh YYmin'."""
    total_minutos = max(round(duracao_segundos / 60.0), 1)
    horas, minutos = divmod(total_minutos, 60)

    if horas and minutos:
        return f"{horas}h {minutos:02d}min"
    if horas:
        return f"{horas}h"
    return f"{total_minutos} min"


def obter_percurso(
    client: httpx.Client, lat_o: float, lon_o: float, lat_d: float, lon_d: float
) -> dict[str, str]:
    """Consulta o OSRM e calcula distância em km e duração de viagem de carro.

    Em caso de trajetos sem estradas (ex: ilhas), coordenadas inválidas ou
    timeout (6.0s), retorna dicionário com fallback descritivo
    ('Sem rota direta' / 'Considere voos ou barcos').
    """
    fallback: dict[str, str] = {
        "distancia": "Sem rota direta",
        "tempo": "Considere voos ou barcos",
        "duracao": "Considere voos ou barcos",
    }

    origem = _coordenada_normalizada(lat_o, lon_o)
    destino = _coordenada_normalizada(lat_d, lon_d)
    if origem is None or destino is None:
        return fallback

    lat_origem, lon_origem = origem
    lat_destino, lon_destino = destino
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{lon_origem},{lat_origem};{lon_destino},{lat_destino}"
    )

    try:
        if client is not None:
            resposta = client.get(url, params={"overview": "false"}, timeout=6.0)
        else:
            with httpx.Client(timeout=6.0) as default_client:
                resposta = default_client.get(url, params={"overview": "false"})

        if resposta.status_code != 200:
            return fallback

        try:
            dados = resposta.json()
        except ValueError:
            return fallback

        if not isinstance(dados, dict) or dados.get("code") != "Ok":
            return fallback

        rotas = dados.get("routes")
        if not isinstance(rotas, list) or not rotas:
            return fallback

        rota_principal = rotas[0]
        if not isinstance(rota_principal, dict):
            return fallback

        distancia_metros = _medida_positiva(rota_principal.get("distance"))
        duracao_segundos = _medida_positiva(rota_principal.get("duration"))
        if distancia_metros is None or duracao_segundos is None:
            return fallback

        dist_km = distancia_metros / 1000.0
        distancia_str = f"{dist_km:.1f} km" if dist_km >= 1 else f"{dist_km:.2f} km"

        total_minutos = max(round(duracao_segundos / 60.0), 1)

        return {
            "distancia": distancia_str,
            "tempo": formatar_duracao(duracao_segundos),
            "duracao": f"{total_minutos} min",
        }
    except (requests.RequestException, httpx.HTTPError, KeyError, ValueError, TypeError):
        return fallback
