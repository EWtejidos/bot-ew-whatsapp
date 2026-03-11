def detect_mood(text):
    if not text:
        return "neutral"

    normalized = text.lower().strip()

    positive_words = {
        "bien",
        "feliz",
        "contento",
        "contenta",
        "excelente",
        "genial",
        "super",
        "motivado",
        "motivada",
        "agradecido",
        "agradecida",
        "tranquilo",
        "tranquila",
    }

    negative_words = {
        "mal",
        "triste",
        "cansado",
        "cansada",
        "estresado",
        "estresada",
        "ansioso",
        "ansiosa",
        "deprimido",
        "deprimida",
        "enojado",
        "enojada",
        "aburrido",
        "aburrida",
        "no muy bien",
        "podría estar mejor",
        "bien no estoy",
        "no me siento bien",
        "bien no"
        "bien no me siento",
        "no bien"
    }

    positive_hits = sum(1 for word in positive_words if word in normalized)
    negative_hits = sum(1 for word in negative_words if word in normalized)

    if positive_hits > negative_hits:
        return "positive"
    if negative_hits > positive_hits:
        return "negative"
    return "neutral"


def build_mood_reply(mood):
    if mood == "positive":
        return "Me alegra saber que te sientes bien  ."
    if mood == "negative":
        return "Gracias por compartirlo. \n tal vez no sea el mejor día pero recuerda las palabras de la Lic. Karina…\nLevanta ese rostro autóctono, esa tez humilde que cuenta historia y dignidad.\nLevántate, porque nadie te va a levantar mejor que tú.\nNo te rebajes por nadie.\nEsa cara arriba, porque tú no eres cualquier cosa."
    return "Gracias por compartirlo.\n tal vez no sea el mejor día pero recuerda las palabras de la Lic. Karina…\nLevanta ese rostro autóctono, esa tez humilde que cuenta historia y dignidad.\nLevántate, porque nadie te va a levantar mejor que tú.\nNo te rebajes por nadie.\nEsa cara arriba, porque tú no eres cualquier cosa."
