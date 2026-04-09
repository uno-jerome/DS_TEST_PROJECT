/*
SQLyog Ultimate v12.4.1 (64 bit)
MySQL - 10.3.17-MariaDB : Database - itc_database_admin
*********************************************************************
*/

/*!40101 SET NAMES utf8 */;

/*!40101 SET SQL_MODE=''*/;

/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/`itc_database_admin` /*!40100 DEFAULT CHARACTER SET utf8 */;

USE `itc_database_admin`;

/*Table structure for table `customers` */

DROP TABLE IF EXISTS `customers`;

CREATE TABLE `customers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(100) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `contact_number` varchar(50) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `registered_at` datetime DEFAULT current_timestamp(),
  `failed_login_count` int(11) DEFAULT 0,
  `last_failed_login` datetime DEFAULT NULL,
  `account_locked` tinyint(1) DEFAULT 0,
  `locked_until` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8;

/*Data for the table `customers` */

insert  into `customers`(`id`,`email`,`username`,`password_hash`,`name`,`contact_number`,`address`,`registered_at`,`failed_login_count`,`last_failed_login`,`account_locked`,`locked_until`) values 
(1,'goodvoy0303@!gmail.com','buyer1','1a802e06ab01bb8d102cc6815ab5a337566e3bf727492c0bac91b4ad4a18992e','Jerome Ruiz','+639924877371','178 Sulucan Address','2026-04-08 19:33:10',0,NULL,0,NULL),
(2,'goodvoy0303@gmail.com','buyer2','pbkdf2_sha256$260000$f1d04a19feda811256106aa1d15002c0$83532d0f18ea8e8d77f0bbbeb88aabac35b2b1355dd23afe59fdfb41e4725578','Jerome Ruiz','+639924877371','12313','2026-04-08 21:07:11',0,NULL,0,NULL);

/*Table structure for table `inventory` */

DROP TABLE IF EXISTS `inventory`;

CREATE TABLE `inventory` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` varchar(200) DEFAULT NULL,
  `price` int(11) DEFAULT NULL,
  `stock` int(11) DEFAULT NULL,
  `size` varchar(50) DEFAULT NULL,
  `date_created` date DEFAULT NULL,
  `date_updated` date DEFAULT NULL,
  `is_deleted` int(1) DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

/*Data for the table `inventory` */

/*Table structure for table `order_items` */

DROP TABLE IF EXISTS `order_items`;

CREATE TABLE `order_items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `order_id` bigint(20) DEFAULT NULL,
  `item_id` varchar(50) DEFAULT NULL,
  `quantity` int(11) DEFAULT NULL,
  `price` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8;

/*Data for the table `order_items` */

insert  into `order_items`(`id`,`order_id`,`item_id`,`quantity`,`price`) values 
(1,1,'754-D',1,32000.00),
(2,2,'754-D',1,32000.00),
(3,3,'754-D',1,32000.00),
(4,4,'754-D',1,32000.00),
(5,5,'754-D',1,32000.00),
(6,6,'754-D',1,32000.00),
(7,7,'754-D',1,32000.00),
(8,8,'754-D',1,32000.00),
(9,8,'754-D',1,32000.00),
(10,9,'311-A',1,35000.00),
(11,9,'754-D',1,32000.00);

/*Table structure for table `orders` */

DROP TABLE IF EXISTS `orders`;

CREATE TABLE `orders` (
  `order_id` bigint(20) NOT NULL,
  `customer_name` varchar(100) DEFAULT NULL,
  `total_amount` decimal(10,2) DEFAULT NULL,
  `order_date` datetime DEFAULT current_timestamp(),
  `status` varchar(50) DEFAULT 'Pending',
  `vat_amount` decimal(10,2) DEFAULT 0.00,
  `grand_total` decimal(10,2) DEFAULT 0.00,
  `payment_method` varchar(50) DEFAULT 'Cash',
  `contact_number` varchar(50) DEFAULT NULL,
  `customer_address` varchar(255) DEFAULT NULL,
  `customer_email` varchar(100) DEFAULT NULL,
  `customer_username` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

/*Data for the table `orders` */

insert  into `orders`(`order_id`,`customer_name`,`total_amount`,`order_date`,`status`,`vat_amount`,`grand_total`,`payment_method`,`contact_number`,`customer_address`,`customer_email`,`customer_username`) values 
(1,'jerome',32000.00,'2026-04-08 16:47:13','Pending',0.00,0.00,'Cash',NULL,NULL,NULL,NULL),
(2,'Jerome',32000.00,'2026-04-08 16:50:34','Pending',0.00,0.00,'Cash',NULL,NULL,NULL,NULL),
(3,'Jerome Ruiz',32000.00,'2026-04-08 17:21:37','Pending',3840.00,35840.00,'Credit/Debit Card',NULL,NULL,NULL,NULL),
(4,'Jerome Ruiz',32000.00,'2026-04-08 17:36:51','Pending',3840.00,35840.00,'Cash','09924877371','178 Sulucan street, Santa Maria Bulacan',NULL,NULL),
(5,'Ruiz, Jerome G.',32000.00,'2026-04-08 17:48:20','Processing',3840.00,35840.00,'Cash','+639924877371','Test',NULL,NULL),
(6,'Jerome Ruiz',32000.00,'2026-04-08 18:28:02','Pending',3840.00,35840.00,'Cash','+639924877371','178 Sulucan Street, Santa Maria Bulacan',NULL,NULL),
(7,'JEromme',32000.00,'2026-04-08 18:35:02','Pending',3840.00,35840.00,'Cash','+639924877371','178 TEST TEST','goodvoy0303@gmail.com','buyer2'),
(8,'Jerome Ruiz',64000.00,'2026-04-08 19:34:54','Pending',7680.00,71680.00,'Cash','+639924877371','178 Sulucan Address','goodvoy0303@!gmail.com','buyer1'),
(9,'Jerome Ruiz',67000.00,'2026-04-08 23:40:58','Pending',8040.00,75040.00,'PayMaya','+639924877371','12313','goodvoy0303@gmail.com','buyer2');

/*Table structure for table `product_details` */

DROP TABLE IF EXISTS `product_details`;

CREATE TABLE `product_details` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `item_id` varchar(50) NOT NULL,
  `description` text DEFAULT NULL,
  `specs_json` text DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `return_policy_text` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `item_id` (`item_id`),
  UNIQUE KEY `ux_product_details_item_id` (`item_id`),
  CONSTRAINT `fk_product_details_item_id` FOREIGN KEY (`item_id`) REFERENCES `stocks` (`item_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8;

/*Data for the table `product_details` */

insert  into `product_details`(`id`,`item_id`,`description`,`specs_json`,`image_path`,`return_policy_text`) values 
(1,'981-A','TEST PRODUCT','TEST PRODUCT','D:/Downloads/Color Hunt Palette 091413285a48408a71b0e4cc.png','N/a'),
(2,'293-C','TEST',NULL,'D:/Downloads/Color Hunt Palette 091413285a48408a71b0e4cc.png',NULL),
(3,'549-I','TEST image',NULL,'D:/Downloads/Color Hunt Palette 091413285a48408a71b0e4cc.png',NULL),
(4,'825-E','Huge 16″ SMB laptop with AI-accelerated Intel® Core™ Ultra processors\n\nSpeedy response time, all-day battery life, & instant wake with Intel Evo™ Edition\n\nIncludes numeric pad for convenient data entry & number crunching\n\nEnables seamless video calls with rich visuals & noise-canceling audio\n\nIdeal for demanding tasks like data analysis, financial modeling, and video conferencing',NULL,'D:/Downloads/nlp7hjbit9r7qbqb941hykxjino4f3761364.png',NULL),
(5,'672-B','Processor AMD Ryzen™ 5 7535HS Processor (3.30 GHz up to 4.55 GHz)\nOperating System Windows 11 Home Single Language 64\nGraphic Card NVIDIA® GeForce RTX™ 3050 Laptop GPU 6GB GDDR6\nMemory 16 GB DDR5-4800MT/s (SODIMM)\nStorage 512 GB SSD M.2 2242 PCIe Gen4 QLC\nDisplay 15.6\" FHD (1920 x 1080), IPS, Anti-Glare, Non-Touch, 100%sRGB, 300 nits, 144Hz\n720P HD with Dual Microphone\nNo Storage Selection\n3 Cell Rechargeable Li-ion 57.5Wh\nAC Adapter and Power Supply icon 135W Slim 30% PCC 3Pin AC Adapter - US\nNo Fingerprint Reader\nKeyboard Grey - English (US)\nWi-Fi 6 2x2 AX & Bluetooth® 5.3\nWarranty 1 Year Courier or Carry-in\nColor Luna Grey',NULL,'D:/Downloads/g76lrjx54hgzcxxapjvosd4oqm9nb9322790.png',NULL);

/*Table structure for table `products` */

DROP TABLE IF EXISTS `products`;

CREATE TABLE `products` (
  `ProductID` int(11) NOT NULL,
  `ProductName` varchar(100) DEFAULT NULL,
  `Price` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`ProductID`),
  KEY `idx_ProductName` (`ProductName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

/*Data for the table `products` */

/*Table structure for table `sales` */

DROP TABLE IF EXISTS `sales`;

CREATE TABLE `sales` (
  `SaleID` int(11) NOT NULL,
  `ProductID` int(11) DEFAULT NULL,
  `Quantity` int(11) DEFAULT NULL,
  `SaleDate` date NOT NULL,
  PRIMARY KEY (`SaleDate`,`SaleID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

/*Data for the table `sales` */

/*Table structure for table `stocks` */

DROP TABLE IF EXISTS `stocks`;

CREATE TABLE `stocks` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `item_id` varchar(50) NOT NULL,
  `name` mediumtext DEFAULT NULL,
  `price` mediumtext DEFAULT NULL,
  `quantity` mediumtext DEFAULT NULL,
  `category` mediumtext DEFAULT NULL,
  `date` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ux_stocks_item_id` (`item_id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8;

/*Data for the table `stocks` */

insert  into `stocks`(`id`,`item_id`,`name`,`price`,`quantity`,`category`,`date`) values 
(6,'754-D','Huawei Matebook D15','32,000','11','Premium Laptops','2024-10-24 15:57:58'),
(9,'881-A','Macbook Neo','33900.0','50','Mainstream Laptops','2026-04-08 22:20:52'),
(10,'871-A','KZZI Mechanical Keyboard','1500.0','250','Peripherals','2026-04-08 22:41:29'),
(11,'311-A','31231','35000.0','24','Premium Laptops','2026-04-08 23:07:46'),
(12,'981-A','TEST','3211','12','Mainstream Laptops','2026-04-09 01:06:04'),
(13,'293-C','TEST','3211','1','Mainstream Laptops','2026-04-09 01:14:20'),
(14,'549-I','TEST','1','12','Peripherals','2026-04-09 01:27:17'),
(15,'825-E','ThinkBook 16 Gen 7 16\" Intel','102000','350','Premium Laptops','2026-04-09 01:37:13'),
(16,'672-B','Lenovo LOQ Essential 15ARP10','67448.79','100','Premium Laptops','2026-04-09 15:25:37');

/*Table structure for table `students` */

DROP TABLE IF EXISTS `students`;

CREATE TABLE `students` (
  `id` int(11) DEFAULT NULL,
  `name` text DEFAULT NULL,
  `grade` char(1) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

/*Data for the table `students` */

/*Table structure for table `users` */

DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` varchar(20) DEFAULT 'admin',
  `failed_login_count` int(11) DEFAULT 0,
  `last_failed_login` datetime DEFAULT NULL,
  `account_locked` tinyint(1) DEFAULT 0,
  `locked_until` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8;

/*Data for the table `users` */

insert  into `users`(`id`,`username`,`password`,`role`,`failed_login_count`,`last_failed_login`,`account_locked`,`locked_until`) values 
(1,'admin','pbkdf2_sha256$260000$a95245b73f1cf84ac6e73c2b5861d8c2$82d9946ee4b7446c41e64300a94b9bd7b5f0b5b401cca004299a35cd7f592eaa','admin',0,NULL,0,NULL);

/*Table structure for table `vw_salesreport` */

DROP TABLE IF EXISTS `vw_salesreport`;

/*!50001 DROP VIEW IF EXISTS `vw_salesreport` */;
/*!50001 DROP TABLE IF EXISTS `vw_salesreport` */;

/*!50001 CREATE TABLE  `vw_salesreport`(
 `ProductName` varchar(100) ,
 `Quantity` int(11) ,
 `SaleDate` date ,
 `TotalSale` decimal(20,2) 
)*/;

/*View structure for view vw_salesreport */

/*!50001 DROP TABLE IF EXISTS `vw_salesreport` */;
/*!50001 DROP VIEW IF EXISTS `vw_salesreport` */;

/*!50001 CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_salesreport` AS select `p`.`ProductName` AS `ProductName`,`s`.`Quantity` AS `Quantity`,`s`.`SaleDate` AS `SaleDate`,`s`.`Quantity` * `p`.`Price` AS `TotalSale` from (`sales` `s` join `products` `p` on(`s`.`ProductID` = `p`.`ProductID`)) */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
