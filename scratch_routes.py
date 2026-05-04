
from app.main import app
from starlette.routing import Route, Mount

def print_routes(routes, prefix=""):
    for route in routes:
        if isinstance(route, Route):
            print(f"{route.methods} {prefix}{route.path}")
        elif isinstance(route, Mount):
            try:
                print_routes(route.app.routes, prefix + route.path)
            except AttributeError:
                print(f"MOUNT {prefix}{route.path}")

print_routes(app.routes)
