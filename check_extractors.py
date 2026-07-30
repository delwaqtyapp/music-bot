from yt_dlp.extractor import list_extractors
for info in list_extractors():
    name = info.get('ie_key', '')
    if 'snap' in name.lower():
        print(f"IE_KEY: {name}")
