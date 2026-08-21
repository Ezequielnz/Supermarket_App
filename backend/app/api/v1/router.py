from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, lists, orders, products, supermarkets

router = APIRouter()
router.include_router(auth.router)
router.include_router(products.router)
router.include_router(lists.router)
router.include_router(orders.router)
router.include_router(supermarkets.router)
router.include_router(admin.router)
