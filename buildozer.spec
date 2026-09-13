[app]

title = AstroFlow
package.name = astroflow
package.domain = org.durolipons
source.dir = .
source.include_exts = py,kv,json,jpg,png,txt,ttf,pdf,html
source.exclude_dirs = tests,Reference,docs,.venv,__pycache__,.git,scripts,.pytest_cache,recipes
version = 0.1.0
requirements = python3,kivy==2.3.1,pyswisseph,astropy,astroquery,jplephem
orientation = portrait
fullscreen = 0

android.presplash_color = #FFFFFF
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.entrypoint = org.kivy.android.PythonActivity
android.apptheme = "@android:style/Theme.NoTitleBar"
android.logcat_filters = *:S python:D
android.archs = arm64-v8a

# Local p4a recipes directory — provides custom recipes for C extensions
# (e.g. pyswisseph) that don't have built-in p4a recipes
p4a.local_recipes = ./recipes

[buildozer]
log_level = 2
warn_on_root = 0


