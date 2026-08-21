from fastapi import APIRouter

from app.api.v1.endpoints import auth, lists, orders, products

router = APIRouter()
router.include_router(auth.router)
router.include_router(products.router)
router.include_router(lists.router)
router.include_router(orders.router)

# Futuro (sprint del panel de supermercado): supermarkets (admin)
