import { Router, type IRouter } from "express";
import healthRouter from "./health";
import districtsRouter from "./districts";

const router: IRouter = Router();

router.use(healthRouter);
router.use(districtsRouter);

export default router;
