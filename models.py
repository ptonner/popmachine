from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Enum, Float
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

Base = declarative_base()

class Project(Base):
	__tablename__ = "projects"
	id = Column(Integer, primary_key=True)
	name = Column(String)
	plates = relationship("Plate",back_populates="project")

class Plate(Base):
	__tablename__ = "plates"
	id = Column(Integer, primary_key=True)
	name = Column(String)
	data_table = Column(String)
	wells = relationship("Well",back_populates="plate")
	project_id = Column(Integer, ForeignKey('projects.id'))
	project = relationship("Project", back_populates="plates")

	# no two plates in the same project can share a name
	__table_args__ = (UniqueConstraint('name','project_id', name='_name_project_uc'),
                     )

	def __repr__(self):
		return "Plate: %s" % self.name

class Well(Base):
	__tablename__ = "wells"
	id = Column(Integer, primary_key=True)
	plate_id = Column(Integer, ForeignKey('plates.id'))
	plate = relationship("Plate", back_populates="wells")
	plate_number = Column(Integer)
	quantities = relationship("ChemicalQuantity",back_populates="well")
	design_values = relationship("DesignValue",back_populates="well")

	def __repr__(self):
		return "%d, %s" % (self.plate_number,self.plate.name)

class Design(Base):
	__tablename__ = "designs"
	id = Column(Integer, primary_key=True)
	name = Column(String,unique=True)
	type = Column(Enum("str","int","float",'bool'))
	values = relationship("DesignValue",back_populates="design")

	def __repr__(self):
		return "%s (%s)" % (self.name,self.type)

class DesignValue(Base):
	__tablename__ = "design_element"
	id = Column(Integer, primary_key=True)
	design_id = Column(Integer,ForeignKey("designs.id"))
	design = relationship("Design",back_populates="values")
	well_id = Column(Integer,ForeignKey("wells.id"))
	well = relationship("Well",back_populates="design_values")
	value = Column(String)

	# each well should only have one value of any single design
	__table_args__ = (UniqueConstraint('well_id','design_id', name='_well_design_uc'),)

	def get_value(self):
		if self.design.type == 'str':
			return str(self.value)
		elif self.design.type == 'int':
			return int(self.value)
		elif self.design.type == 'float':
			return float(self.value)
		elif self.design.type == 'bool':
			return bool(self.value)

	def __repr__(self):
		return "%s %s" % (self.value,self.design.name)

class Chemical(Base):
	__tablename__ = "chemicals"
	id = Column(Integer, primary_key=True)
	name = Column(String,unique=True)
	abbreviation = Column(String,unique=True)
	quantities = relationship("ChemicalQuantity",back_populates="chemical")

	def __repr__(self):
		return "%s (%s)" % (self.name, self.abbreviation)

class ChemicalQuantity(Base):
	__tablename__ = "chemical_quantities"
	id = Column(Integer, primary_key=True)
	type = Column(Enum("concentration","mass by volume","percent mass","percent volume"))
	chemical_id = Column(Integer, ForeignKey("chemicals.id"))
	chemical = relationship("Chemical",back_populates="quantities")
	well_id = Column(Integer, ForeignKey("wells.id"))
	well = relationship("Well",back_populates="quantities")
	value = Column(Float)

	# each well should only have one quantity of any single chemical
	__table_args__ = (UniqueConstraint('well_id','chemical_id', name='_well_chemical_uc'),
                     )

	def parse(self,s):
		value,_,chemical = s.split(" ")
		return value == self.value and (chemical==self.chemical.name or chemical==self.chemical.abbreviation)

	def __repr__(self):
		if self.type == "concentration":
			if self.chemical.abbreviation and self.chemical.abbreviation != "":
				return "%.2lf mM %s (%s)" % (self.value, self.chemical.abbreviation,self.well)
			else:
				return "%.2lf mM %s (%s)" % (self.value, self.chemical.name,self.well)

class Strain(Base):
	__tablename__ = "strains"
	id = Column(Integer, primary_key=True)
	name = Column(String)
	pubmed_id = Column(Integer)
	parent_id = Column(Integer, ForeignKey('strains.id'))
	children = relationship("Strain",
			backref=backref('parent', remote_side=[id])
		)

	def __repr__(self):
		if self.parent:
			return "%s (%s)" % (self.name , self.parent.name)
		else:
			return "%s" % self.name
