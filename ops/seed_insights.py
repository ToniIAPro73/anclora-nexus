"""Seed NotebookLM insights using the configured Neon database."""
from dotenv import load_dotenv

load_dotenv()

from datetime import datetime, timezone
from backend.services.neon_service import neon_service

db = neon_service.client

ORG_ID = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
NOTEBOOK_ID = "9f003773-16c5-4fb4-ab37-7b6c230ab4da"
NOTEBOOK_NAME = "Inteligencia Territorial Suroeste Mallorca 2026"
NOW = datetime.now(timezone.utc).isoformat()

insights = [
    {
        "org_id": ORG_ID,
        "notebook_id": NOTEBOOK_ID,
        "notebook_name": NOTEBOOK_NAME,
        "insight_type": "territorial",
        "zona": "general",
        "query": "Analisis completo del mercado inmobiliario del Suroeste de Mallorca 2026: tendencias, demanda internacional, perfil comprador, zonas activas y oportunidades de captacion.",
        "response": (
            "El mercado balear cerro 2025 liderando el IPV espanol con +13,4% interanual. "
            "Segmento lujo/superlujo (+2,5M EUR) proyecta crecimiento 5-8% en 2026. "
            "Descuento sobre precio de salida: 0% en zonas prime; guerras de pujas en activos trofeo, venta en 30-60 dias. "
            "60-70% de adquisiciones en superlujo al contado. Comprador prime: edad media 46 anos (emprendedores tech, profesionales globales). "
            "Alemanes lideran (59% transacciones prime), pero capital estadounidense es motor de crecimiento (+20-30% gasto vs media europea), "
            "facilitados por vuelos directos NY-Palma. Costa d'en Blanes: vacancia cero, 10.185 EUR/m2, +21% interanual. "
            "Port d'Andratx: 9.027-9.339 EUR/m2, propiedades primera linea 15-30M EUR. "
            "El Toro: +13,3% (7.515 EUR/m2) por regeneracion Port Adriano. "
            "Mandarin Oriental Punta Negra 2026: efecto halo +33-39% en propiedades adyacentes. "
            "Estrategias clave: off-market en Costa d'en Blanes/Andratx, value-add en El Toro, "
            "green premium +15-20% con certificacion A/B, apartamentos lujo para nomadas digitales (alquileres +7,4%)."
        ),
        "metadata": {
            "source": "notebooklm_mcp",
            "conversation_id": "5d4d876b-800b-449f-a2bf-a696cf47251c",
            "zones_covered": ["general", "costa_den_blanes", "port_adriano", "el_toro", "punta_negra"],
        },
        "created_at": NOW,
    },
    {
        "org_id": ORG_ID,
        "notebook_id": NOTEBOOK_ID,
        "notebook_name": NOTEBOOK_NAME,
        "insight_type": "territorial",
        "zona": "andratx",
        "query": "Andratx y Port Adriano: mercado, precios, compradores, senales de vendedores motivados y oportunidades de captacion 2026.",
        "response": (
            "Port d'Andratx: 8.921-9.339 EUR/m2, villas primera linea 15-30M EUR, 0% descuento, 60-70% transacciones al contado. "
            "Andratx Pueblo: +13,1% interanual (4.061 EUR/m2), tendencia autenticidad vs saturacion costera. "
            "Camp de Mar: ajuste tecnico -27,6% (7.072 EUR/m2) por cambio composicion inventario post-obra-nueva, no perdida de valor intrinseco. "
            "Comprador UHNWI, edad media 46 anos, emprendedores tech. Afluencia critica compradores estadounidenses (+20-30% gasto). "
            "Captacion off-market: contacto directo presentando perfiles UHNWI cash-ready. "
            "Argumento clave: transacciones cero dias en mercado (privacidad). "
            "El Toro (influencia Port Adriano): 7.515 EUR/m2, +13,3% interanual. "
            "Senales FSBO: villas anticuadas sin renovar cuyos propietarios no pueden asumir costes construccion; "
            "propiedades sin certificacion energetica A/B pierden competitividad (premium verde +15-20%)."
        ),
        "metadata": {
            "source": "notebooklm_mcp",
            "conversation_id": "7a985365-a9ca-4b70-ab5a-a58c476d9adb",
            "zones_covered": ["andratx", "port_adriano", "el_toro"],
        },
        "created_at": NOW,
    },
    {
        "org_id": ORG_ID,
        "notebook_id": NOTEBOOK_ID,
        "notebook_name": NOTEBOOK_NAME,
        "insight_type": "territorial",
        "zona": "calvia",
        "query": "Calvia, Santa Ponca, Son Ferrer y Paguera: analisis de mercado, precios, stock, dias en mercado y oportunidades FSBO 2026.",
        "response": (
            "Calvia: precio medio 7.014 EUR/m2, +5,2% interanual. "
            "Santa Ponca: 7.041 EUR/m2, +7,6% interanual, alta demanda expatriados britanicos/alemanes, activos 300k-2M EUR. "
            "Paguera: 6.148 EUR/m2, +3,7% interanual, repunte mensual +4,8% feb-2026 (aceleracion demanda). "
            "Son Ferrer: 5.548 EUR/m2, -5,3% interanual (-8,6% desde maximo ago-2025) - anomalia tecnica, objetivo value-add. "
            "Velocidad mercado: propiedades turnkey se venden en 30-60 dias; tiempo medio mercado menos de 6 meses. "
            "Descuento negociacion: 0% en zonas prime Calvia. 60-70% transacciones al contado. "
            "Estrategias FSBO: (1) Off-market Santa Ponca/Paguera - presentar compradores USA/alemanes/nordicos con liquidez inmediata; "
            "(2) Value-Add Son Ferrer - efecto catch-up vs El Toro (+13,3%), captar villas estancadas para inversores reposicionamiento; "
            "(3) Green Premium - propiedades A/B obtienen +15-20% precio, proponer retrofit solar antes de salir a mercado; "
            "(4) Nomadas digitales - alquileres +7,4%, yield hasta 5% bruto en Calvia/Palma."
        ),
        "metadata": {
            "source": "notebooklm_mcp",
            "conversation_id": "b3d30a6d-290a-49b2-95ed-31392e5b1c02",
            "zones_covered": ["calvia", "santa_ponca", "son_ferrer", "paguera"],
        },
        "created_at": NOW,
    },
    {
        "org_id": ORG_ID,
        "notebook_id": NOTEBOOK_ID,
        "notebook_name": NOTEBOOK_NAME,
        "insight_type": "territorial",
        "zona": "portals_nous",
        "query": "Portals Nous, Bendinat, Punta Negra y Costa d'en Blanes: precios, perfil comprador, senales vendedores motivados y captacion premium 2026.",
        "response": (
            "Costa d'en Blanes: 9.677-10.185 EUR/m2, +21-22,2% interanual, vacancia cero, inelasticidad pura (0% descuento). "
            "Portals Nous / Bendinat: 8.350-8.558 EUR/m2, fase consolidacion post-boom, variaciones anuales planas o ligeramente negativas (-3,3% a +0,4%). "
            "Punta Negra: catalizador predictivo - apertura Mandarin Oriental 2026 genera efecto halo +33-39% en propiedades adyacentes. "
            "Comprador prime: edad media 46 anos, semi-relocators (hasta 6 meses/ano), emprendedores tech. "
            "Compradores USA: +20-30% gasto, villas lock-up-and-leave 5-8M EUR llave en mano con domotica estandar americano. "
            "60-70% transacciones sin financiacion. "
            "Senales vendedores motivados: (1) Bendinat - propietarios villas grandes compradas pre-2020 motivados para asegurar ganancias de capital; "
            "(2) Periferia Punta Negra - propiedades que necesitan actualizacion cuyos duenos quieren capitalizar efecto Mandarin pero sin liquidez para reforma. "
            "Estrategias captacion: off-market Costa d'en Blanes (UHNWI cash-ready); "
            "valor anadido + green premium +15-20% en Portals/Bendinat; "
            "apartamentos lujo para inversores yield (nomadas digitales, ejecutivos)."
        ),
        "metadata": {
            "source": "notebooklm_mcp",
            "conversation_id": "0901b835-4d45-4e68-8404-cbe57fa08bb5",
            "zones_covered": ["portals_nous", "bendinat", "punta_negra", "costa_den_blanes"],
        },
        "created_at": NOW,
    },
    {
        "org_id": ORG_ID,
        "notebook_id": NOTEBOOK_ID,
        "notebook_name": NOTEBOOK_NAME,
        "insight_type": "whale_audit",
        "zona": "general",
        "query": "Senales de vendedores motivados (FSBO, dias en mercado elevados) y argumentos de captacion para convencer a un propietario particular de trabajar con un agente eXp.",
        "response": (
            "Senales predictivas vendedores motivados: "
            "(1) DOM elevado - propiedades turnkey se venden en 30-60 dias en zonas prime; activo por encima de ese rango = sobreprecio o falta modernizacion; "
            "(2) Inventario obsoleto en zonas catch-up - villas antiguas sin renovar en El Toro/Magaluf donde no pueden capitalizar apreciacion sin inversion; "
            "(3) Sin certificacion energetica A/B - propiedades sin instalaciones solares/sostenibles perdiendo competitividad frente a compradores HNWI jovenes. "
            "Argumentos captacion vs FSBO para agente eXp: "
            "(1) Acceso compradores UHNW internacionales - 70% transacciones lujo al contado; capital USA +20-30% gasto, vuelos directos NY; el FSBO no tiene acceso a este capital; "
            "(2) Green Premium pre-comercializacion - demostrar ROI: certificaciones A/B o renovaciones sostenibles = +15-20% precio final; coordinar retrofit solar antes de listar; "
            "(3) Redes off-market - en +10M EUR, gran parte de transacciones son off-market por privacidad; portales publicos no son el canal; redes internacionales cerradas solo accesibles a agentes conectados globalmente; "
            "(4) Blindaje legal/regulatorio - Ley de Vivienda 2026, licencias alquiler turistico, auditorias urbanisticas en Baleares; operar sin representacion expone al vendedor a riesgos costosos."
        ),
        "metadata": {
            "source": "notebooklm_mcp",
            "conversation_id": "a2cf98bb-f84b-4a45-9817-217077cdb2bf",
            "zones_covered": ["general"],
            "use_case": "whale_dossier_argumentario",
        },
        "created_at": NOW,
    },
]

# Clear old seed data and insert fresh
db.table("notebooklm_insights").delete().eq("org_id", ORG_ID).execute()
print("Old insights cleared.")

result = db.table("notebooklm_insights").insert(insights).execute()
print(f"Inserted {len(result.data)} insights:")
for row in result.data:
    print(f"  [{row['zona']:15}] {row['insight_type']:12} → {row['id'][:8]}...")

print("\nDone.")
