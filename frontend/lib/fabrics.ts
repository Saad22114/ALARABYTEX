import { Fabric } from '@/types';

export function rollSaleAllowed(fabric: Fabric | undefined | null, branchId?: number | null): boolean {
  if (!fabric || branchId == null) return false;
  const override = fabric.roll_sale_overrides?.[String(branchId)];
  return override === true;
}
