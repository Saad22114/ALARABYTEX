import { Fabric } from '@/types';

export function rollSaleAllowed(fabric: Fabric | undefined | null, branchId?: number | null): boolean {
  if (!fabric) return true;
  if (branchId != null) {
    const key = String(branchId);
    const override = fabric.roll_sale_overrides?.[key];
    if (typeof override === 'boolean') return override;
  }
  return fabric.allow_roll_sale !== false;
}