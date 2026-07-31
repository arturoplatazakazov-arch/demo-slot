"""Domain services shared by the API layer, the simulator and the admin
builder: ORM-config -> engine adapters, grid/response formatting, popup
selection and grid post-processing. FastAPI-free — depends only on
app.engine / app.features / app.models, so non-API consumers
(app/simulator, app/api/admin/builder_config.py) can use it without
importing the HTTP layer."""
